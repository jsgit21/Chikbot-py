#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/chikbot
UNIT=chikbot

# Wrapped in main() so bash parses the whole script before running any of it:
# the git pull below rewrites this file while it is executing.
main() {
    local branch before after reqs_before reqs_after
    local restarts_before restarts_after baseline state

    if [ ! -d "$APP_DIR" ]; then
        echo "deploy: $APP_DIR does not exist" >&2
        exit 1
    fi

    if ! git -C "$APP_DIR" rev-parse --git-dir >/dev/null 2>&1; then
        echo "deploy: $APP_DIR is not a git repository" >&2
        exit 1
    fi

    if [ -n "$(git -C "$APP_DIR" status --porcelain)" ]; then
        echo "deploy: $APP_DIR has uncommitted changes, refusing to pull" >&2
        git -C "$APP_DIR" status --short >&2
        exit 1
    fi

    branch="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)"
    if [ "$branch" != "main" ]; then
        echo "deploy: $APP_DIR is on '$branch', expected 'main'" >&2
        exit 1
    fi

    before="$(git -C "$APP_DIR" rev-parse HEAD)"
    reqs_before="$(sha256sum "$APP_DIR/requirements.txt" | cut -d ' ' -f 1)"

    git -C "$APP_DIR" pull --ff-only

    after="$(git -C "$APP_DIR" rev-parse HEAD)"
    if [ "$before" = "$after" ]; then
        echo "deploy: already up to date at ${after:0:8}, not restarting"
        exit 0
    fi

    reqs_after="$(sha256sum "$APP_DIR/requirements.txt" | cut -d ' ' -f 1)"
    if [ "$reqs_before" != "$reqs_after" ]; then
        echo "deploy: requirements.txt changed, reinstalling dependencies"
        "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
    fi

    restarts_before="$(systemctl show "$UNIT" -p NRestarts --value)"

    sudo systemctl restart "$UNIT"

    sleep 5

    state="$(systemctl is-active "$UNIT" || true)"
    restarts_after="$(systemctl show "$UNIT" -p NRestarts --value)"

    # systemd zeroes NRestarts on a manual start, so a count below the pre-deploy
    # one means the counter reset and every restart since then is ours.
    baseline="$restarts_before"
    if [ "$restarts_after" -lt "$restarts_before" ]; then
        baseline=0
    fi

    if [ "$state" != "active" ] || [ "$restarts_after" -gt "$baseline" ]; then
        echo "deploy: $UNIT is unhealthy after restart (state=$state, NRestarts $restarts_before -> $restarts_after)" >&2
        journalctl -u "$UNIT" -n 40 --no-pager >&2
        exit 1
    fi

    echo "deploy: $UNIT active, deployed ${before:0:8} -> ${after:0:8}"
    git -C "$APP_DIR" log --oneline "$before..$after"
    journalctl -u "$UNIT" -n 20 --no-pager
}

main "$@"
