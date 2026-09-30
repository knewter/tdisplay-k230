# The board glass keeps its native portrait axes when it drives an external
# monitor. wlroots applies the mapped output transform to absolute contacts;
# compensate before that step so glass x/y still become logical x/y.
# Sway CLI transforms are clockwise; wlroots stores the inverse Wayland enum.
# This calibration applies only while the touchscreen is mapped to HDMI.
transform:
{
  normal = "1 0 0 0 1 0";
  "90" = "0 -1 1 1 0 0";
  "180" = "-1 0 1 0 -1 1";
  "270" = "0 1 0 -1 0 1";
}.${transform}
