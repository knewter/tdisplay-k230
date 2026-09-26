#ifndef K230_CARD_SHELL_POLICY_H
#define K230_CARD_SHELL_POLICY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Product policy only: never stores a view, surface, buffer, title, or app text.
 * IDs are compositor-owned, nonzero, and must not be reused during a session.
 * Unknown classification must be CS_UNAVAILABLE, never inferred to be live. */
enum cs_content { CS_UNAVAILABLE, CS_PRIVATE, CS_LIVE };
struct cs_card {
    uint64_t id;
    enum cs_content content;
    bool focusable;
    bool closeable;
};
enum cs_mode { CS_NORMAL, CS_DECK, CS_DRAGGING, CS_CLOSING, CS_ENTERING, CS_EXPANDING };
enum cs_message {
    CS_MESSAGE_NONE, CS_MESSAGE_EMPTY, CS_MESSAGE_PRIVATE,
    CS_MESSAGE_UNAVAILABLE, CS_MESSAGE_CLOSING, CS_MESSAGE_CLOSE_REFUSED,
    CS_MESSAGE_CLOSE_TIMEOUT, CS_MESSAGE_CLOSE_FAILED, CS_MESSAGE_CANCELLED,
    CS_MESSAGE_SOURCE_GONE, CS_MESSAGE_FAILED
};
enum cs_actions {
    CS_NO_ACTION = 0, CS_REDRAW = 1 << 0, CS_SHRINK = 1 << 1,
    CS_EXPAND = 1 << 2, CS_RESTORE = 1 << 3, CS_CLOSE = 1 << 4,
    CS_RECONCILE = 1 << 5
};
struct cs_result {
    unsigned actions;
    bool consumed;
    uint64_t focus_id; /* 0 means focus a valid workspace, never a stale view. */
    uint64_t close_id; /* Nonzero only alongside CS_CLOSE. Dispatch once. */
    uint64_t source_gone_id; /* Unmap/removal is NOT process exit proof. */
    enum cs_message message;
};
struct cs_rect { double x, y, width, height; };
/* Bound small: only ever walked back a few steps for a recency-biased
 * velocity estimate, never grown for its own sake. */
#define CS_ENTRY_HISTORY_CAP 8
struct cs_entry_touch_sample { double x, y; uint64_t t; };
struct cs_config {
    double width, height;
    double top_reserved, bottom_reserved; /* bar and keyboard; never intercepted */
    double inset, gap, title_height, footer_height;
    /* card_width/card_height/gap are the OVERVIEW's own focused-card slot:
     * an Android-recents-sized card, 80% of the panel's width AND 80% of
     * its height (same fraction on both axes, so the card's aspect ratio
     * matches the panel's own), with neighbours peeking only a thin sliver
     * at the screen edges -- revised 2026-09-26 per the operator's explicit
     * "more like Android does" request and
     * docs/design/shell-polish-review-2026-09.md's overview section,
     * superseding the prior 2026-09-25 webOS-fan pass (50%/60%, 2-3 cards
     * visible across) recorded in design.md decision 1 of
     * the-shell-behaves-as-one-coherent-system. These are deliberately
     * independent of entry_card_width/entry_card_height below: the direct
     * bottom-edge app-switch gesture's anchor/travel geometry must not move
     * when the overview's card size changes. */
    double card_width, card_height;
    /* Vertical anchor for cs_card_rect's y, replacing a fixed `inset` there
     * (inset itself is unchanged and still used elsewhere, including
     * cs_entry_target_rect, so this cannot perturb entry geometry): chosen
     * by the caller so the icon+name header (drawn above the card by
     * adapter.c/render.c, a rendering-only concern this field does not
     * track directly) plus the card vertically centers in the space
     * between the title and the footer, instead of sitting flush under
     * the title. See card-shell-policy.c's cs_default_config and
     * adapter.c's matching runtime recompute for the actual formula. */
    double card_top_offset;
    /* The single centered slot the direct-switch entry gesture tracks
     * (cs_entry_target_rect): historically the same value as card_width/
     * card_height, now kept as its own field so shrinking the overview's
     * fan cards cannot perturb entry_travel/entry_anchor_shift or the
     * mid-drag "full-size neighbour" feel. */
    double entry_card_width, entry_card_height;
    double edge_band, entry_distance, tap_slop;
    double throw_distance, throw_speed; /* logical pixels/ms */
    /* Entry (edge-swipe app switch) lateral gate, kept separate from the
     * in-deck select_fraction above: a fraction of the full screen width,
     * not of the card pitch, and a release-velocity flick threshold in
     * logical pixels/ms. See card-shell-policy.c cs_entry_up_at. */
    double entry_select_fraction, entry_flick_speed;
    uint64_t close_timeout_ms;
    bool reduced_motion; /* Direct tracking/endpoints are identical either way. */
	bool touch_first_motion; /* Opt-in live entry/expansion; rollback keeps old route. */
};
struct cs_policy {
    struct cs_config config;
    struct cs_card *cards;
    size_t count, selected;
    enum cs_mode mode;
    enum cs_message message;
    uint64_t saved_focus_id, pressed_id, closing_id, close_deadline_ms;
    bool contact, blocked_until_up;
    unsigned blocked_contacts;
    int32_t contact_id;
    double down_x, down_y, last_x, last_y, dx, dy, velocity_y, velocity_x;
    uint64_t last_time_ms;
    double velocity_origin_y, velocity_origin_x;
    uint64_t velocity_origin_ms;
    /* Overview horizontal-scroll momentum: a released drag continues to
     * coast dx toward the newly-selected card's rest position (0) instead
     * of snapping there instantly, projecting the resting card from the
     * release velocity so a fast flick can carry several cards, not just
     * the adjacent one. See card-shell-policy.c cs_up/cs_tick and
     * touch_window_span (shared with the entry gesture's own estimator). */
    bool scroll_settling;
    double scroll_from_dx, scroll_release_velocity, scroll_duration;
    uint64_t scroll_started_ms;
    /* Recent raw touch samples for the overview drag's own recency-biased
     * release-velocity estimate -- same shape and window as entry_history
     * below, reused via touch_window_span, but a separate buffer: the two
     * gestures run independently and must never share state. */
    struct cs_entry_touch_sample scroll_history[CS_ENTRY_HISTORY_CAP];
    size_t scroll_history_count;
	/* 0 displays the original view geometry; 1 displays its deck slot. */
	double entry_progress;
	uint64_t entry_id;
	/* The projected source point under the accepted finger reaches its card
	 * counterpart after this many logical pixels; commitment is separate. */
	double entry_travel, entry_drag;
	struct cs_rect entry_full_rect;
	/* Snapshot preserves visual order through focus-only switches and maps. */
	uint64_t *entry_order;
	size_t entry_count, entry_origin;
	uint64_t entry_left_id, entry_right_id, entry_target_id;
	double entry_dx, entry_raw_dx, entry_anchor_shift, entry_anchor_factor;
	/* Vertical analog of entry_anchor_shift: corrects cs_entry_visual_rect's
	 * y interpolation for the gap between entry_card_height (what
	 * entry_travel/the anchor fraction were established against) and the
	 * overview's own, independently-sized card_height -- see
	 * cs_entry_set_geometry and cs_entry_visual_rect. Zero whenever the two
	 * heights coincide. */
	double entry_anchor_shift_y;
	double entry_release_dx, entry_settle_dx, entry_reverse_dx, entry_reverse_anchor;
	double entry_reverse_from;
	double entry_settle_from;
	double entry_goal_progress, entry_settle_anchor;
	double entry_release_velocity_x, entry_release_velocity_progress;
	double entry_sample_x, entry_sample_y;
	uint64_t entry_sample_ms;
	/* Recent raw touch samples for a recency-biased release-velocity
	 * estimate: a single stale/instantaneous last delta is unreliable, but
	 * averaging over a long fixed window would blur a genuine last-instant
	 * reversal. cs_entry_release_velocity() walks back only as far as it
	 * needs to (see card-shell-policy.c). */
	struct cs_entry_touch_sample entry_history[CS_ENTRY_HISTORY_CAP];
	size_t entry_history_count;
	uint64_t entry_started_ms;
	/* When entry_interrupted_hold began (the interrupting touch-down's own
	 * time_ms) -- bounds how long cs_tick may freeze the entry animation
	 * for a held interrupting contact. Without a bound, a chain of
	 * closely-spaced touches (e.g. a tap, then a flick, then another tap,
	 * each landing before the previous one's up is processed) can hold the
	 * transition frozen for seconds instead of the ~240ms it is meant to
	 * take: see cs_tick's own comment and docs/evidence/card-shell/
	 * video-card-gestures/. */
	uint64_t entry_interrupt_started_ms;
	bool entry_reversing, entry_settling, entry_interrupted_hold;
	double expand_progress, expand_reverse_from;
	uint64_t expand_id, expand_started_ms;
	/* A policy tick dwell at full geometry; not output presentation proof. */
	bool expand_reversing, expand_full_dwell;
    enum { CS_AXIS_NONE, CS_AXIS_HORIZONTAL, CS_AXIS_VERTICAL } axis;
    struct {
        bool tracking;
        int32_t contact_id;
        double x, y;
        uint64_t time_ms;
    } edge;
};

/* Defaults are provisional product constants, not measured hardware claims.
 * Recompute card dimensions after changing keyboard reservation. */
struct cs_config cs_default_config(double width, double height);
bool cs_init(struct cs_policy *policy, const struct cs_config *config);
void cs_finish(struct cs_policy *policy);
/* Copies a complete caller snapshot. Any count is accepted subject to allocation.
 * Duplicate/zero IDs or allocation failure abort to normal with FAILED feedback.
 * Call before scene access on map/unmap/destroy/privacy/output changes. */
struct cs_result cs_set_cards(struct cs_policy *policy,
    const struct cs_card *cards, size_t count);
struct cs_result cs_set_config(struct cs_policy *policy,
    const struct cs_config *config);
struct cs_result cs_enter(struct cs_policy *policy, uint64_t focused_id);
struct cs_result cs_leave(struct cs_policy *policy);
/* Persistent button equivalents; direction must be -1 or +1. */
struct cs_result cs_step(struct cs_policy *policy, int direction);
struct cs_result cs_request_close(struct cs_policy *policy, uint64_t id,
    uint64_t time_ms);
struct cs_result cs_down(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms);
struct cs_result cs_motion(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms);
struct cs_result cs_up(struct cs_policy *policy, int32_t contact_id,
    uint64_t time_ms);
/* Local rejection: swallow remaining hardware contacts through their ups. */
struct cs_result cs_cancel(struct cs_policy *policy);
/* Compositor touch_cancel/device removal: the entire stream has ended and no
 * further up is guaranteed. Clear all contact, edge and drain state so the next
 * stream can begin. Safe deck position is restored; pending close is separate. */
struct cs_result cs_stream_cancel(struct cs_policy *policy);
struct cs_result cs_tick(struct cs_policy *policy, uint64_t time_ms);
/* Only the adapter can know an explicit refusal or failed dispatch; otherwise
 * tick reports timeout while the source remains present. Neither force-kills. */
struct cs_result cs_close_result(struct cs_policy *policy, uint64_t id,
    bool refused);

/* Normal-mode edge recognition: reserve the bottom band, then enter only on an
 * upward single-contact swipe. Passing an app's already delivered touch stream
 * into this recognizer without cancelling that app stream is forbidden.
 * The adapter must own/reserve the edge down from the start. */
struct cs_result cs_edge_down(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms);
struct cs_result cs_edge_motion(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms, uint64_t focused_id);
struct cs_result cs_edge_up(struct cs_policy *policy, int32_t contact_id);
/* Touch-first entry keeps the live compositor mirror under the finger.
 * Early/reversed release restores the application without a deck endpoint. */
struct cs_result cs_begin_entry(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms, uint64_t focused_id);
/* Called once from the compositor's live-source/card geometry reconciliation.
 * Source and target coordinates are output-local logical pixels. */
bool cs_entry_set_geometry(struct cs_policy *policy, double source_x,
    double source_y, double source_width, double source_height,
    double target_x, double target_y, double target_width,
    double target_height);
struct cs_result cs_entry_motion(struct cs_policy *policy, int32_t contact_id,
    double x, double y, uint64_t time_ms);
struct cs_result cs_entry_up(struct cs_policy *policy, int32_t contact_id);
struct cs_result cs_entry_up_at(struct cs_policy *policy, int32_t contact_id,
    uint64_t time_ms);
/* Local edge rejection only; for a complete stream use cs_stream_cancel. */
void cs_edge_cancel(struct cs_policy *policy);

bool cs_can_mirror(const struct cs_policy *policy, uint64_t id);
struct cs_rect cs_content_rect(const struct cs_policy *policy);
struct cs_rect cs_card_rect(const struct cs_policy *policy, size_t index);
/* The single centered slot the direct-switch (bottom-edge entry) gesture
 * anchors/travels against -- entry_card_width/entry_card_height, never the
 * overview's own (possibly much smaller) card_width/card_height. Call this,
 * not cs_card_rect, to build cs_entry_set_geometry's target argument. */
struct cs_rect cs_entry_target_rect(const struct cs_policy *policy);
/* Geometry of one live or neutral carousel slot during app entry. Source is
 * the output-local full view rectangle; no pixels or titles enter policy. */
struct cs_rect cs_entry_visual_rect(const struct cs_policy *policy,
    size_t index, struct cs_rect source, bool common_full_frame);
/* Returns SIZE_MAX outside cards/content clip. Adapter buttons are hit first. */
size_t cs_hit_test(const struct cs_policy *policy, double x, double y);
const char *cs_message_text(enum cs_message message);
const char *cs_card_text(enum cs_content content); /* safe placeholder labels */

#endif
