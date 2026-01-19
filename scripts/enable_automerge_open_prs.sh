#!/usr/bin/env bash
set -euo pipefail

OWNER="${OWNER:-Notoriousjayy}"
MERGE_METHOD="${MERGE_METHOD:-squash}"   # squash|merge|rebase
LIMIT_REPOS="${LIMIT_REPOS:-200}"
LIMIT_PRS="${LIMIT_PRS:-200}"
SLEEP_S="${SLEEP_S:-0.2}"               # small delay helps avoid secondary limits

# Safety filters (optional)
ONLY_HEAD_PREFIX="${ONLY_HEAD_PREFIX:-}"  # e.g. "autofix/" to only target your autofix branches
ONLY_AUTHOR="${ONLY_AUTHOR:-}"            # e.g. "dependabot[bot]"

merge_flag="--squash"
case "$MERGE_METHOD" in
  squash) merge_flag="--squash" ;;
  merge)  merge_flag="--merge"  ;;
  rebase) merge_flag="--rebase" ;;
  *) echo "Invalid MERGE_METHOD: $MERGE_METHOD (use squash|merge|rebase)"; exit 2 ;;
esac

echo "Owner=$OWNER merge_method=$MERGE_METHOD repo_limit=$LIMIT_REPOS pr_limit=$LIMIT_PRS"
echo "Filters: ONLY_HEAD_PREFIX='$ONLY_HEAD_PREFIX' ONLY_AUTHOR='$ONLY_AUTHOR'"

repos="$(gh repo list "$OWNER" --limit "$LIMIT_REPOS" --json name -q '.[].name')"

while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  full="$OWNER/$repo"
  echo "==== $full ===="

  # Pull minimal PR data, filter with jq for speed and to avoid drafts.
  prs_json="$(gh pr list -R "$full" --state open --limit "$LIMIT_PRS" \
    --json number,isDraft,headRefName,author,autoMergeRequest \
    2>/dev/null || true)"

  echo "$prs_json" | jq -r '
    .[]
    | select(.isDraft == false)
    | select(.autoMergeRequest == null)
    | "\(.number)\t\(.headRefName)\t\(.author.login)"
  ' | while IFS=$'\t' read -r pr head author; do
        [ -z "$pr" ] && continue

        if [ -n "$ONLY_HEAD_PREFIX" ] && [[ "$head" != "$ONLY_HEAD_PREFIX"* ]]; then
          continue
        fi
        if [ -n "$ONLY_AUTHOR" ] && [ "$author" != "$ONLY_AUTHOR" ]; then
          continue
        fi

        echo "Enabling auto-merge: $full#$pr ($head by $author)"
        # This enables auto-merge (and will wait for required checks/reviews).
        # If already mergeable, it may merge immediately (by design).
        gh pr merge -R "$full" "$pr" --auto $merge_flag --delete-branch \
          || echo "WARN: failed to enable auto-merge for $full#$pr"

        sleep "$SLEEP_S"
      done

done <<< "$repos"

echo "Done."
