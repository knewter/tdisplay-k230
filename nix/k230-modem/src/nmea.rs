//! NMEA for gpsd. The Serial LTE Modem 2.9.0 on the base has no NMEA
//! output: it reports GNSS through `#XGPS:` URCs (board probe 2026-10-26,
//! `docs/evidence/nrf9151/gnss-rate/`). A fix is turned into GGA and RMC
//! sentences here. `#XGNSSNMEA:` from older firmware is still accepted.

/// Extract the sentence from a `#XGNSSNMEA:` URC line.
/// UNVERIFIED on hardware: the quoting of the payload. Both a bare and a
/// quoted payload are accepted.
pub fn parse_urc(line: &str) -> Option<String> {
    let rest = line.strip_prefix("#XGNSSNMEA:")?.trim();
    let rest = rest.strip_prefix('"').and_then(|r| r.strip_suffix('"')).unwrap_or(rest);
    let rest = rest.trim_end_matches(['\r', '\n']);
    if rest.starts_with('$') && checksum_ok(rest) {
        Some(rest.to_string())
    } else {
        None
    }
}

/// One `#XGPS:` URC.
#[derive(Debug, Clone, PartialEq)]
pub enum Xgps {
    /// `#XGPS: <gnss_service>,<gnss_status>`: 0 stopped, 1 started,
    /// 2 periodic wake-up, 3 sleeping after a timeout, 4 sleeping after a fix.
    Status(u32),
    /// A fix, as NMEA GGA and RMC sentences.
    Fix(Vec<String>),
}

/// Parse a `#XGPS:` URC. A fix reads
/// `<lat>,<lon>,<alt>,<accuracy>,<speed>,<heading>,"<YYYY-MM-DD hh:mm:ss>"`
/// with degrees, metres and metres per second.
/// UNVERIFIED on hardware: no fix had been seen when this was written; the
/// form follows the SLM 2.9 documentation.
pub fn parse_xgps(line: &str) -> Option<Xgps> {
    let rest = line.strip_prefix("#XGPS:")?.trim();
    let f: Vec<&str> = rest.split(',').map(str::trim).collect();
    if f.len() == 2 {
        return f[1].parse().ok().map(Xgps::Status);
    }
    if f.len() < 7 {
        return None;
    }
    let num = |i: usize| f.get(i).and_then(|v| v.parse::<f64>().ok());
    let (lat, lon) = (num(0)?, num(1)?);
    if !(-90.0..=90.0).contains(&lat) || !(-180.0..=180.0).contains(&lon) {
        return None;
    }
    let alt = num(2).unwrap_or(0.0);
    let speed_knots = num(4).unwrap_or(0.0) * 1.943_844;
    let heading = num(5).unwrap_or(0.0);
    let when = f[6..].join(",");
    let when = when.trim_matches('"');
    let (date, time) = when.split_once(' ')?;
    let d: Vec<&str> = date.split('-').collect();
    if d.len() != 3 || d[0].len() != 4 {
        return None;
    }
    let hms: String = time.split('.').next()?.chars().filter(|c| c.is_ascii_digit()).collect();
    if hms.len() != 6 {
        return None;
    }
    let ddmmyy = format!("{}{}{}", d[2], d[1], &d[0][2..]);
    let angle = |v: f64, deg_w: usize, pos: char, neg: char| {
        let a = v.abs();
        let deg = a.trunc();
        let min = (a - deg) * 60.0;
        (format!("{:0deg_w$}{:07.4}", deg as u32, min), if v < 0.0 { neg } else { pos })
    };
    let ((la, ns), (lo, ew)) = (angle(lat, 2, 'N', 'S'), angle(lon, 3, 'E', 'W'));
    Some(Xgps::Fix(vec![
        with_checksum(&format!("GPGGA,{hms}.00,{la},{ns},{lo},{ew},1,,,{alt:.1},M,,M,,")),
        with_checksum(&format!("GPRMC,{hms}.00,A,{la},{ns},{lo},{ew},{speed_knots:.1},{heading:.1},{ddmmyy},,,A")),
    ]))
}

/// True when there is no checksum, or when it matches.
pub fn checksum_ok(sentence: &str) -> bool {
    let Some(body) = sentence.strip_prefix('$') else { return false };
    match body.split_once('*') {
        None => true,
        Some((data, cs)) => {
            cs.trim().len() == 2
                && u8::from_str_radix(cs.trim(), 16).map(|c| c == data.bytes().fold(0u8, |a, b| a ^ b)).unwrap_or(false)
        }
    }
}

/// `Some(true)` for a sentence that reports a fix, `Some(false)` for one
/// that reports none, `None` for sentences that say nothing about it.
pub fn fix_status(sentence: &str) -> Option<bool> {
    let body = sentence.strip_prefix('$')?.split('*').next()?;
    let f: Vec<&str> = body.split(',').collect();
    let kind = f.first()?;
    if kind.ends_with("GGA") {
        let q: u32 = f.get(6)?.parse().unwrap_or(0);
        return Some(q > 0);
    }
    if kind.ends_with("RMC") {
        return Some(*f.get(2)? == "A");
    }
    None
}

/// Frame a sentence body with `$` and its checksum (used by fixtures).
pub fn with_checksum(body: &str) -> String {
    format!("${body}*{:02X}", body.bytes().fold(0u8, |a, b| a ^ b))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_bare_and_quoted_and_rejects_bad_checksums() {
        let s = with_checksum("GPGGA,000000.00,0100.0000,N,00100.0000,E,0,00,99.9,0.0,M,,M,,");
        assert_eq!(parse_urc(&format!("#XGNSSNMEA: {s}")).as_deref(), Some(s.as_str()));
        assert_eq!(parse_urc(&format!("#XGNSSNMEA: \"{s}\"")).as_deref(), Some(s.as_str()));
        let bad = s.replace('*', "*0");
        assert_eq!(parse_urc(&format!("#XGNSSNMEA: {bad}")), None);
        assert_eq!(parse_urc("+CEREG: 90"), None);
    }

    #[test]
    fn xgps_status_and_fix_become_state_and_nmea() {
        assert_eq!(parse_xgps("#XGPS: 1,1"), Some(Xgps::Status(1)));
        assert_eq!(parse_xgps("#XGPS: 1,3"), Some(Xgps::Status(3)));
        let Some(Xgps::Fix(s)) = parse_xgps("#XGPS: -1.500000,-100.250000,12.5,4.2,0.5,90.0,\"2026-10-26 12:34:56\"") else {
            panic!("no fix")
        };
        assert_eq!(s.len(), 2);
        assert!(s[0].starts_with("$GPGGA,123456.00,0130.0000,S,10015.0000,W,1,,,12.5,M"), "{}", s[0]);
        assert!(s[1].starts_with("$GPRMC,123456.00,A,0130.0000,S,10015.0000,W,1.0,90.0,261026,"), "{}", s[1]);
        assert!(s.iter().all(|x| checksum_ok(x)));
        assert_eq!(fix_status(&s[0]), Some(true));
        assert_eq!(parse_xgps("#XGPS: 91.0,0,0,0,0,0,\"2026-10-26 12:34:56\""), None);
        assert_eq!(parse_xgps("#XGPS: 1"), None);
    }

    #[test]
    fn fix_status_from_gga_and_rmc() {
        assert_eq!(fix_status("$GPGGA,0,0100.0,N,00100.0,E,0,00,99.9,0.0,M,,M,,*00"), Some(false));
        assert_eq!(fix_status("$GPGGA,0,0100.0,N,00100.0,E,1,05,1.0,0.0,M,,M,,*00"), Some(true));
        assert_eq!(fix_status("$GNRMC,0,V,,,,,,,,,,N*00"), Some(false));
        assert_eq!(fix_status("$GPGSV,1,1,00*00"), None);
    }
}
