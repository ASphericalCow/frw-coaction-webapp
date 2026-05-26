#!/usr/bin/env bash
# Cold-start measurement run for Cloud Run deployment.
# Launches 12 samples with 25-min idle gaps. ~5 hr total.

URL="https://frw-coaction-webapp-358241706213.europe-west4.run.app"
N=12
WAIT=1500   # 25 min between samples
OUT_DIR="$(cd "$(dirname "$0")" && pwd)/cold_start_results"
mkdir -p "$OUT_DIR"
STAMP="$(date '+%Y%m%d_%H%M%S')"
RAW="$OUT_DIR/raw_${STAMP}.tsv"
LOG="$OUT_DIR/log_${STAMP}.txt"

{
  echo "Cold-start test"
  echo "URL: $URL"
  echo "Samples: $N | idle between samples: $((WAIT/60)) min"
  echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Output: $RAW"
  echo
} | tee "$LOG"

# TSV header
printf "sample\twait_s\tcold_ttfb_s\tcold_total_s\twarm_ttfb_s\twarm_total_s\tcold_http\twarm_http\n" > "$RAW"

for i in $(seq 1 "$N"); do
  echo "[$(date '+%H:%M:%S')] Sample $i/$N — idle wait $((WAIT/60)) min..." | tee -a "$LOG"
  sleep "$WAIT"

  # Cold request
  COLD=$(curl -s -o /dev/null -w "%{time_starttransfer}\t%{time_total}\t%{http_code}" "$URL")
  sleep 3
  # Warm follow-up
  WARM=$(curl -s -o /dev/null -w "%{time_starttransfer}\t%{time_total}\t%{http_code}" "$URL")

  COLD_TTFB=$(echo "$COLD" | cut -f1)
  COLD_TOTAL=$(echo "$COLD" | cut -f2)
  COLD_HTTP=$(echo "$COLD" | cut -f3)
  WARM_TTFB=$(echo "$WARM" | cut -f1)
  WARM_TOTAL=$(echo "$WARM" | cut -f2)
  WARM_HTTP=$(echo "$WARM" | cut -f3)

  printf "%d\t%d\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$i" "$WAIT" "$COLD_TTFB" "$COLD_TOTAL" "$WARM_TTFB" "$WARM_TOTAL" "$COLD_HTTP" "$WARM_HTTP" >> "$RAW"
  echo "  cold: TTFB=${COLD_TTFB}s total=${COLD_TOTAL}s | warm: TTFB=${WARM_TTFB}s total=${WARM_TOTAL}s" | tee -a "$LOG"
done

echo | tee -a "$LOG"
echo "Done: $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG"
echo | tee -a "$LOG"

# Quick summary
awk -F'\t' 'NR>1 {
  c[NR-1]=$4; w[NR-1]=$6; n=NR-1;
  if(min_c==""||$4<min_c) min_c=$4;
  if(max_c==""||$4>max_c) max_c=$4;
  if(min_w==""||$6<min_w) min_w=$6;
  if(max_w==""||$6>max_w) max_w=$6;
  sc+=$4; sw+=$6;
}
END {
  if(n==0) { print "no data"; exit }
  mc=sc/n; mw=sw/n;
  for(i=1;i<=n;i++){ vc+=(c[i]-mc)^2; vw+=(w[i]-mw)^2 }
  sdc=(n>1)?sqrt(vc/(n-1)):0;
  sdw=(n>1)?sqrt(vw/(n-1)):0;
  printf "Cold total (s): mean=%.3f  sd=%.3f  min=%.3f  max=%.3f  (n=%d)\n", mc, sdc, min_c, max_c, n;
  printf "Warm total (s): mean=%.3f  sd=%.3f  min=%.3f  max=%.3f  (n=%d)\n", mw, sdw, min_w, max_w, n;
}' "$RAW" | tee -a "$LOG"
