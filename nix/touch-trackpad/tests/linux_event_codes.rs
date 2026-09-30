//! Compare our hand-bound codes with independently compiled Linux headers.
#[path = "../src/event.rs"]
mod event;

#[test]
fn touchpad_button_codes_match_linux_headers() {
    use std::io::Write;
    use std::process::{Command, Stdio};

    let executable = std::env::temp_dir().join(format!("k230-event-uapi-{}", std::process::id()));
    let mut compiler = Command::new("cc")
        .args(["-x", "c", "-", "-o"])
        .arg(&executable)
        .stdin(Stdio::piped())
        .spawn()
        .expect("host UAPI check requires cc and Linux input headers");
    compiler.stdin.take().unwrap().write_all(br#"
#include <linux/input-event-codes.h>
#include <stdio.h>
int main(void) {
    printf("%u %u %u %u %u %u\n", BTN_LEFT, BTN_TOUCH,
           BTN_TOOL_FINGER, BTN_TOOL_DOUBLETAP,
           BTN_TOOL_TRIPLETAP, BTN_TOOL_QUADTAP);
    return 0;
}
"#).unwrap();
    assert!(compiler.wait().unwrap().success());
    let output = Command::new(&executable).output().unwrap();
    std::fs::remove_file(&executable).unwrap();
    assert!(output.status.success());
    let kernel_codes: Vec<u16> = std::str::from_utf8(&output.stdout).unwrap()
        .split_whitespace().map(|v| v.parse().unwrap()).collect();
    assert_eq!(kernel_codes, vec![event::BTN_LEFT, event::BTN_TOUCH,
        event::BTN_TOOL_FINGER, event::BTN_TOOL_DOUBLETAP,
        event::BTN_TOOL_TRIPLETAP, event::BTN_TOOL_QUADTAP]);
}
