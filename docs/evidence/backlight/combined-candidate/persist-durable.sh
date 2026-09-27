#!/usr/bin/env bash
# Run ONLY on the reserved board, under a detached systemd oneshot after
# physical acceptance. Arguments: TARGET NEW_BUNDLE PREVIOUS_BUNDLE UNIQUE_RUN_DIR
# No fallback if the existing system profile is missing. No reboot or activation.
# NON-ATOMIC: direct /boot overwrites avoid a second ~88 MiB bundle on its
# 112 MiB partition. Power loss/SIGKILL can leave mixed or incomplete files.
# Keep normal boot prohibited until final verification. Recover via U-Boot
# one-shot loading the verified rootfs candidate/backup; never saveenv.
set -Eeuo pipefail
set -f
umask 077
export PATH=/run/current-system/sw/bin:/run/wrappers/bin
export LC_ALL=C
unset CDPATH

[[ $# -eq 4 ]] || { printf 'usage: %s TARGET NEW PREVIOUS UNIQUE_RUN_DIR\n' "$0" >&2; exit 64; }
target=$1; new=$2; previous=$3; run=$4
[[ $target =~ ^/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+$ ]] || exit 64
for path in "$new" "$previous" "$run"; do
    [[ $path =~ ^/var/lib/k230/[A-Za-z0-9/._-]+$ && $path != *'/../'* && $path != */.. && $path != */. ]] || exit 64
done
[[ $run != "$new" && $run != "$previous" ]] || exit 64
[[ ${run##*/} =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$ ]] || exit 64
[[ $EUID -eq 0 ]] || { printf 'root required\n' >&2; exit 77; }
# mkdir without -p intentionally refuses an existing run or symlink.
mkdir -m 0700 -- "$run"
exec >>"$run/transaction.log" 2>&1

phase=initializing
failure_code=command_failed
failure_line=0
started=0
finished=0
profile_before=
backup_system=
rollback_state=not_needed
run_tag=${run##*/}
profile=/nix/var/nix/profiles/system
boot_files=(Image initrd.uimg k230-tdisplay.dtb bootargs.txt)
fixed_files=(fw_jump_add_uboot_head.bin force_dtb lcd_dtb hdmi_dtb)

write_result() {
    local status=$1 code=$2
    # All string fields are constants or validated restricted paths.
    printf '{"schema":1,"atomic_boot_update":false,"status":"%s","exit_status":%s,"phase":"%s","failure_code":"%s","failure_line":%s,"target":"%s","profile_before":"%s","backup_system":"%s","boot_mutation_started":%s,"rollback":"%s"}\n' \
        "$status" "$code" "$phase" "$failure_code" "$failure_line" "$target" \
        "$profile_before" "$backup_system" "$started" "$rollback_state" >"$run/result.json.tmp" || return
    mv -- "$run/result.json.tmp" "$run/result.json" || return
    sync
}
finish() {
    local code=$? restore_failed=0 status=FAILED_BEFORE_BOOT_MUTATION
    trap - EXIT ERR
    trap '' HUP INT TERM
    set +e
    printf 'EXIT phase=%s status=%s line=%s\n' "$phase" "$code" "$failure_line"
    if [[ $code -eq 0 && $finished -eq 1 ]]; then
        status=SUCCESS
        failure_code=none
    else
        [[ $code -ne 0 ]] || code=70
        if [[ $started -eq 1 ]]; then
            printf 'ROLLBACK_BEGIN\n'
            for name in "${boot_files[@]}"; do
                cp --reflink=never --sparse=never -- "$previous/$name" "/boot/$name" || restore_failed=1
                cmp -- "$previous/$name" "/boot/$name" || restore_failed=1
                sync || restore_failed=1
            done
            # Restore exactly the validated prior profile, never a preview.
            nix-env --profile "$profile" --set "$profile_before" || restore_failed=1
            (cd /boot && sha256sum -c "$previous/SHA256SUMS") || restore_failed=1
            [[ $(readlink -e "$profile") == "$profile_before" ]] || restore_failed=1
            sync || restore_failed=1
            if [[ $restore_failed -eq 0 ]]; then
                rollback_state=verified
                status=FAILED_ROLLBACK_VERIFIED
            else
                rollback_state=incomplete
                status=FAILED_ROLLBACK_INCOMPLETE
            fi
        fi
    fi
    if ! write_result "$status" "$code"; then
        printf 'RESULT_WRITE_FAILED status=%s original_exit=%s\n' "$status" "$code"
        [[ $code -ne 0 ]] || code=74
    else
        printf 'K230_PERSIST_FINAL status=%s exit=%s\n' "$status" "$code"
    fi
    exit "$code"
}
trap finish EXIT
trap 'failure_line=$LINENO' ERR
trap 'failure_code=signal_hup; exit 129' HUP
trap 'failure_code=signal_int; exit 130' INT
trap 'failure_code=signal_term; exit 143' TERM
fail() { failure_code=$1; failure_line=${BASH_LINENO[0]}; printf 'FAIL %s phase=%s\n' "$failure_code" "$phase"; exit 1; }
mark() { phase=$1; printf 'PHASE %s\n' "$phase"; printf '%s\n' "$phase" >"$run/phase"; sync; }
valid_store() { [[ $1 =~ ^/nix/store/[a-z0-9]{32}-[A-Za-z0-9+._-]+$ ]]; }
manifest_names() {
    local file=$1 expected=$2 hash name count=0
    local -A seen=()
    [[ -f $file && ! -L $file ]] || fail manifest_missing_or_symlink
    while read -r hash name; do
        [[ $hash =~ ^[a-f0-9]{64}$ ]] || fail malformed_manifest_hash
        name=${name#\*}
        case "$name" in
            Image|initrd.uimg|k230-tdisplay.dtb|bootargs.txt) ;;
            fw_jump_add_uboot_head.bin|force_dtb|lcd_dtb|hdmi_dtb) [[ $expected -eq 8 ]] || fail unexpected_manifest_file ;;
            *) fail unexpected_manifest_file ;;
        esac
        [[ ! ${seen[$name]+yes} ]] || fail duplicate_manifest_file
        seen[$name]=1
        count=$((count + 1))
    done <"$file"
    [[ $count -eq $expected ]] || fail incomplete_manifest
}
boot_target() {
    local file=$1 data word found= count=0
    data=$(<"$file")
    [[ $data == bootargs=* && ${#data} -lt 4096 ]] || return 1
    local -a words=()
    read -r -a words <<<"${data#bootargs=}"
    for word in "${words[@]}"; do
        if [[ $word == init=* ]]; then
            found=${word#init=}; found=${found%/init}; count=$((count + 1))
            [[ $word == "init=$found/init" ]] || return 1
        fi
    done
    [[ $count -eq 1 ]] && valid_store "$found" || return 1
    printf '%s\n' "$found"
}


# Peak usage above the initial installed allocation, with no duplicate bundle.
# Include each completed/partial forward-copy boundary and rollback from every
# such boundary. Restoring a sparse original as dense data is also budgeted.
capacity_peak_growth() {
    local baseline=0 peak=0 used=0 k=0 j=0 i=0 n=${#old_alloc[@]}
    local -a live=()
    for ((i=0; i<n; i++)); do baseline=$((baseline + old_alloc[i])); done
    peak=$baseline
    for ((k=0; k<=n; k++)); do
        live=(); used=0
        for ((i=0; i<n; i++)); do
            if ((i<k)); then live+=("${new_alloc[i]}"); else live+=("${old_alloc[i]}"); fi
            used=$((used + live[i]))
        done
        ((used<=peak)) || peak=$used
        for ((j=0; j<n; j++)); do
            used=$((used - live[j] + restore_alloc[j]))
            live[j]=${restore_alloc[j]}
            ((used<=peak)) || peak=$used
        done
    done
    printf '%s\n' "$((peak - baseline))"
}

mark preflight_tools
for tool in readlink cp mv ln sync sha256sum cmp nix-env flock findmnt stat find; do
    command -v "$tool" >/dev/null || fail required_tool_unavailable
done
# Held by this process, including rollback. Never share a transaction lock.
exec 9>/var/lib/k230/boot-persist.lock
flock -n 9 || fail another_persistence_transaction

mark preflight_identity
[[ $(readlink -e /run/booted-system) == "$target" ]] || fail booted_system_mismatch
[[ $(readlink -e /run/current-system) == "$target" ]] || fail current_system_mismatch
[[ -x $target/init ]] || fail candidate_init_missing
profile_before=$(readlink -e "$profile") || fail prior_profile_missing_or_dangling
if ! valid_store "$profile_before"; then
    profile_before=
    fail prior_profile_not_store_system
fi
[[ -x $profile_before/init ]] || fail prior_profile_init_missing

mark preflight_boot_mount
[[ -b /dev/disk/by-label/K230_BOOT ]] || fail expected_boot_device_missing
mount_source=$(findmnt -rn -M /boot -o SOURCE) || fail boot_not_mounted
[[ $(readlink -e "$mount_source") == $(readlink -e /dev/disk/by-label/K230_BOOT) ]] || fail boot_mount_device_mismatch
[[ $(findmnt -rn -M /boot -o FSTYPE) == ext4 ]] || fail boot_mount_type_mismatch
mount_options=$(findmnt -rn -M /boot -o OPTIONS)
[[ ,$mount_options, == *,rw,* ]] || fail boot_mount_not_writable

mark preflight_bundles
[[ -d $new && ! -L $new && -d $previous && ! -L $previous ]] || fail bundle_directory_missing_or_symlink
manifest_names "$new/SHA256SUMS" 4
manifest_names "$previous/SHA256SUMS" 8
for name in "${boot_files[@]}"; do
    [[ -f $new/$name && ! -L $new/$name ]] || fail candidate_file_missing_or_symlink
done
for name in "${boot_files[@]}" "${fixed_files[@]}"; do
    [[ -f $previous/$name && ! -L $previous/$name ]] || fail backup_file_missing_or_symlink
    [[ -f /boot/$name && ! -L /boot/$name ]] || fail installed_boot_file_missing_or_symlink
done
(cd "$new" && sha256sum -c SHA256SUMS)
(cd "$previous" && sha256sum -c SHA256SUMS)
(cd /boot && sha256sum -c "$previous/SHA256SUMS")
[[ $(boot_target "$new/bootargs.txt") == "$target" ]] || fail candidate_bootargs_mismatch
backup_system=$(boot_target "$previous/bootargs.txt") || fail backup_bootargs_invalid
[[ -x $backup_system/init ]] || fail backup_system_init_missing
cp -- "$new/SHA256SUMS" "$run/candidate.SHA256SUMS"
cp -- "$previous/SHA256SUMS" "$run/previous.SHA256SUMS"
printf '%s\n' "$profile_before" >"$run/profile-before"

mark preserve_roots
ln -s -- "$profile_before" "/nix/var/nix/gcroots/$run_tag-profile-before"
ln -s -- "$backup_system" "/nix/var/nix/gcroots/$run_tag-boot-before"
ln -s -- "$target" "/nix/var/nix/gcroots/$run_tag-candidate"

mark report_boot_staging_remnants
# Record all hidden regular files, but never delete any automatically.
find /boot -maxdepth 1 -type f -name '.*' -printf '%f\t%s\t%b\n' >"$run/boot-hidden-files.tsv"
if [[ -s $run/boot-hidden-files.tsv ]]; then
    printf 'HIDDEN_BOOT_FILES_RECORDED review=%s/boot-hidden-files.tsv\n' "$run"
fi
# The original helper's named partial copies require operator classification.
# Other hidden files remain accounted for in available space, never guessed away.
if [[ -n $(find /boot -maxdepth 1 -name '.k230-panel-next-*' -print -quit) ]]; then
    fail prior_boot_staging_remnants_require_operator_review
fi

mark preflight_rootfs_stage_capacity
root_device=$(stat -c %d /)
for directory in "$run" "$new" "$previous"; do
    [[ $(stat -c %d "$directory") == "$root_device" ]] || fail staging_or_backup_not_on_rootfs
    [[ $(stat -c %d "$directory") != $(stat -c %d /boot) ]] || fail staging_or_backup_on_boot
done
root_fragment=$(stat -f -c %S "$run")
root_available=$(( $(stat -f -c %a "$run") * root_fragment ))
root_required=$((4 * 1024 * 1024)) # metadata/log/headroom, besides candidate files
for name in "${boot_files[@]}"; do
    size=$(stat -c %s "$new/$name")
    root_required=$((root_required + (size + root_fragment - 1) / root_fragment * root_fragment))
done
printf 'ROOTFS_CAPACITY available=%s required=%s\n' "$root_available" "$root_required"
[[ $root_available -ge $root_required ]] || fail insufficient_rootfs_staging_space

mark stage_and_verify_on_rootfs
stage="$run/candidate"
mkdir -m 0700 -- "$stage"
for name in "${boot_files[@]}"; do
    cp --reflink=never --sparse=never -- "$new/$name" "$stage/$name"
done
cp -- "$new/SHA256SUMS" "$stage/SHA256SUMS"
(cd "$stage" && sha256sum -c SHA256SUMS)
sync
# Publish a recovery recipe before any /boot file is touched. These are
# operator instructions, not executed by this helper; existing OpenSBI stays.
{
    printf '%s\n' 'NON-ATOMIC UPDATE: normal boot is prohibited until SUCCESS and fresh verification.'
    printf '%s\n' 'After power loss/interruption, catch U-Boot and one-shot this verified rootfs candidate.'
    printf '%s\n' 'Check every load succeeds; do not saveenv. Inspect/repair /boot from the recovered Linux.'
    printf 'ext4load mmc 1:2 0x7000000 %s/bootargs.txt\n' "$stage"
    printf 'env import -t 0x7000000 0x%x\n' "$(stat -c %s "$stage/bootargs.txt")"
    printf '%s\n' 'ext4load mmc 1:1 0x8000000 /fw_jump_add_uboot_head.bin'
    printf 'ext4load mmc 1:2 0x200000 %s/Image\n' "$stage"
    printf 'ext4load mmc 1:2 0x8400000 %s/k230-tdisplay.dtb\n' "$stage"
    printf 'ext4load mmc 1:2 0x9000000 %s/initrd.uimg\n' "$stage"
    printf '%s\n' 'bootm 0x8000000 0x9000000 0x8400000'
    printf 'Verified previous bundle remains at %s; its own bootargs size must be used if loading it.\n' "$previous"
} >"$run/RECOVERY.txt"
sync

mark preflight_boot_growth_capacity
boot_fragment=$(stat -f -c %S /boot)
boot_available=$(( $(stat -f -c %a /boot) * boot_fragment ))
old_alloc=(); new_alloc=(); restore_alloc=()
printf 'file\told_allocated_bytes\tnew_rounded_bytes\trollback_rounded_bytes\n' >"$run/boot-growth.tsv"
for name in "${boot_files[@]}"; do
    old_bytes=$(( $(stat -c %b "/boot/$name") * 512 ))
    size=$(stat -c %s "$stage/$name")
    new_bytes=$(( (size + boot_fragment - 1) / boot_fragment * boot_fragment ))
    size=$(stat -c %s "$previous/$name")
    restore_bytes=$(( (size + boot_fragment - 1) / boot_fragment * boot_fragment ))
    old_alloc+=("$old_bytes"); new_alloc+=("$new_bytes"); restore_alloc+=("$restore_bytes")
    printf '%s\t%s\t%s\t%s\n' "$name" "$old_bytes" "$new_bytes" "$restore_bytes" >>"$run/boot-growth.tsv"
done
peak_growth=$(capacity_peak_growth)
final_growth=0
for ((i=0; i<${#old_alloc[@]}; i++)); do
    final_growth=$((final_growth + new_alloc[i] - old_alloc[i]))
done
boot_margin=$((2 * 1024 * 1024)) # filesystem metadata/delayed-allocation headroom
boot_required=$((peak_growth + boot_margin))
printf 'BOOT_CAPACITY available=%s final_growth=%s peak_growth_with_rollback=%s margin=%s required=%s\n' \
    "$boot_available" "$final_growth" "$peak_growth" "$boot_margin" "$boot_required"
[[ $boot_available -ge $boot_required ]] || fail insufficient_boot_growth_space

mark overwrite_boot_files_nonatomic
started=1 # arm rollback BEFORE the first truncating copy, not after staging
for name in "${boot_files[@]}"; do
    mark "overwrite_$name"
    cp --reflink=never --sparse=never -- "$stage/$name" "/boot/$name"
    cmp -- "$stage/$name" "/boot/$name"
    sync
    printf 'BOOT_FILE_VERIFIED %s\n' "$name"
done
mark verify_candidate_boot
(cd /boot && sha256sum -c "$stage/SHA256SUMS")
for name in "${fixed_files[@]}"; do cmp -- "$previous/$name" "/boot/$name"; done

mark set_system_profile
nix-env --profile "$profile" --set "$target"
[[ $(readlink -e "$profile") == "$target" ]] || fail installed_profile_mismatch

mark final_verification
(cd /boot && sha256sum -c "$stage/SHA256SUMS")
for name in "${fixed_files[@]}"; do cmp -- "$previous/$name" "/boot/$name"; done
[[ $(readlink -e "$profile") == "$target" ]] || fail final_profile_mismatch
sync
phase=complete
finished=1
# EXIT trap publishes and syncs the durable final outcome before unit exit.
