## Why

On HDMI with a trackpad the operator could not move or remove a Home widget.
A right-click on a widget does nothing: Home's secondary click only opens an
app's menu or, on empty space, the Home menu. Long press is the only way into
rearrange mode, and holding a trackpad button still for half a second is not
something a mouse user tries. Even in rearrange mode a widget has no remove
badge, so removing one means dragging it onto Remove.

## What Changes

- A secondary click on a Home widget enters rearrange mode without picking
  anything up.
- In rearrange mode each widget shows a remove badge at its top-left corner,
  like app icons do. Clicking it removes the widget.
- Moving is unchanged: in rearrange mode, pressing a widget and dragging moves
  it, and Done or a click on empty space leaves rearrange mode.

**Non-goals:** a per-widget context menu, widget settings, or changing how
app icons answer a secondary click.
