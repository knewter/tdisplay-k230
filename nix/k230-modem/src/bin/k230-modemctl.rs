//! k230-modemctl: the command-line client for the k230-modem control socket.

use std::io::{Read, Write};
use std::net::Shutdown;
use std::os::unix::net::UnixStream;
use std::time::Duration;

const USAGE: &str = "usage: k230-modemctl [--socket PATH] status | power on|off | gnss on|off | pin | sms send <number> | sms clear
  pin reads the digits from standard input (never from the command line)
  sms send reads the message body from standard input";

fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut socket = "/run/k230/modem/control".to_string();
    if args.first().map(|a| a == "--socket").unwrap_or(false) {
        if args.len() < 2 {
            eprintln!("{USAGE}");
            std::process::exit(2);
        }
        socket = args[1].clone();
        args.drain(..2);
    }
    let refs: Vec<&str> = args.iter().map(|s| s.as_str()).collect();
    let mut stdin_text = String::new();
    let request = match refs.as_slice() {
        ["status"] | ["power", "on" | "off"] | ["gnss", "on" | "off"] | ["sms", "clear"] => refs.join(" "),
        ["pin"] => {
            let _ = std::io::stdin().read_line(&mut stdin_text);
            format!("pin {}", stdin_text.trim())
        }
        ["sms", "send", number] => {
            let _ = std::io::stdin().read_to_string(&mut stdin_text);
            format!("sms send {number}\n{}", stdin_text.trim_end_matches('\n'))
        }
        _ => {
            eprintln!("{USAGE}");
            std::process::exit(2);
        }
    };

    let mut s = match UnixStream::connect(&socket) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("k230-modemctl: cannot reach the modem service at {socket}: {e}");
            std::process::exit(1);
        }
    };
    let _ = s.set_read_timeout(Some(Duration::from_secs(120)));
    let ok = match request.split_once('\n') {
        Some((line, body)) => s.write_all(format!("{line}\n{body}").as_bytes()),
        None => s.write_all(format!("{request}\n").as_bytes()),
    };
    if let Err(e) = ok {
        eprintln!("k230-modemctl: {e}");
        std::process::exit(1);
    }
    let _ = s.shutdown(Shutdown::Write);
    let mut reply = String::new();
    if let Err(e) = s.read_to_string(&mut reply) {
        eprintln!("k230-modemctl: {e}");
        std::process::exit(1);
    }
    let reply = reply.trim_end();
    if let Some(rest) = reply.strip_prefix("ok") {
        let rest = rest.trim();
        if !rest.is_empty() {
            println!("{rest}");
        }
    } else {
        eprintln!("{}", reply.strip_prefix("err ").unwrap_or(reply));
        std::process::exit(1);
    }
}
