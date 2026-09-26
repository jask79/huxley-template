#!/bin/bash
cd {{CATALYST_ROOT}}/registry

for file in daily/*.json baselines/*.json; do
  if [ -f "$file" ] && grep -iq "lane" "$file"; then
    echo "Processing: $file"
    cp "$file" "$file.lane_backup"
    sed -i '' 's/"fast_lane"/"standard"/g' "$file"
    sed -i '' 's/"deep_lane"/"standard"/g' "$file"
    sed -i '' '/"lane":/d' "$file"
  fi
done

echo "Registry files updated"
