#Terminal Frame
#Obalí Metrics panel do okna terminálu (bodky, milan@github: ~/stats, $ gh stats --profile).
#Použitie: python terminal_frame.py <metrics.svg> <frame.svg> <výstup.svg>
import re
import sys

PANEL_X = 16    #odsadenie panelu zľava
PANEL_Y = 74    #pod lištou a riadkom s príkazom
PAD = 16        #odsadenie dole

panel_path, frame_path, out_path = sys.argv[1:4]
panel = open(panel_path, encoding="utf-8").read()
frame = open(frame_path, encoding="utf-8").read()

#XML hlavička preč, Metrics panel ide dovnútra Terminal Frame
panel = re.sub(r"^\s*<\?xml[^>]*\?>", "", panel)
height = int(float(re.search(r'<svg\b[^>]*?\sheight="([\d.]+)"', panel).group(1)))
panel = re.sub(r"^\s*<svg\b", f'<svg x="{PANEL_X}" y="{PANEL_Y}"', panel, count=1)

total = PANEL_Y + height + PAD
out = (frame.replace("__TOTALM1__", str(total - 1))
            .replace("__TOTAL__", str(total))
            .replace("__PANEL__", panel))
open(out_path, "w", encoding="utf-8").write(out)
print(f"Terminal Frame: panel {height}px, total {total}px")
