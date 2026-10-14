//! NMEA from `#XGNSSNMEA:` URCs.

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
    fn fix_status_from_gga_and_rmc() {
        assert_eq!(fix_status("$GPGGA,0,0100.0,N,00100.0,E,0,00,99.9,0.0,M,,M,,*00"), Some(false));
        assert_eq!(fix_status("$GPGGA,0,0100.0,N,00100.0,E,1,05,1.0,0.0,M,,M,,*00"), Some(true));
        assert_eq!(fix_status("$GNRMC,0,V,,,,,,,,,,N*00"), Some(false));
        assert_eq!(fix_status("$GPGSV,1,1,00*00"), None);
    }
}
