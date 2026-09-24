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
struct cs_config {
    double width, height;
    double top_reserved, bottom_reserved; /* bar and keyboard; never intercepted */
    double inset, gap, title_height, footer_height;
    double card_width, card_height;
    double edge_band, entry_distance, tap_slop;
    double select_fraction, throw_distance, throw_speed; /* logical pixels/ms */
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
    double down_x, down_y, last_x, last_y, dx, dy, velocity_y;
    uint64_t last_time_ms;
    double velocity_origin_y;
    uint64_t velocity_origin_ms;
	/* 0 displays the original view geometry; 1 displays its deck slot. */
	double entry_progress;
	uint64_t entry_id;
	/* The projected source point under the accepted finger reaches its card
	 * counterpart after this many logical pixels; commitment is separate. */
	double entry_travel, entry_drag;
	/* Snapshot preserves visual order through focus-only switches and maps. */
	uint64_t *entry_order;
	size_t entry_count, entry_origin;
	uint64_t entry_left_id, entry_right_id, entry_target_id;
	bool entry_quick_allowed;
	double entry_dx, entry_raw_dx, entry_anchor_shift, entry_anchor_factor;
	double entry_release_dx, entry_settle_dx, entry_reverse_dx, entry_reverse_anchor;
	double entry_reverse_from;
	double entry_settle_from;
	double entry_goal_progress, entry_settle_anchor;
	double entry_velocity_x, entry_velocity_progress;
	double entry_release_velocity_x, entry_release_velocity_progress;
	double entry_sample_x, entry_sample_y;
	uint64_t entry_sample_ms;
	uint64_t entry_started_ms;
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
/* Geometry of one live or neutral carousel slot during app entry. Source is
 * the output-local full view rectangle; no pixels or titles enter policy. */
struct cs_rect cs_entry_visual_rect(const struct cs_policy *policy,
    size_t index, struct cs_rect source);
/* Returns SIZE_MAX outside cards/content clip. Adapter buttons are hit first. */
size_t cs_hit_test(const struct cs_policy *policy, double x, double y);
const char *cs_message_text(enum cs_message message);
const char *cs_card_text(enum cs_content content); /* safe placeholder labels */

#endif
