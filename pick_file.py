import sys
import tkinter as tk
from tkinter import filedialog

sys.stdout.reconfigure(encoding="utf-8")
window = tk.Tk()
window.withdraw()
window.attributes("-topmost", True)
path = filedialog.askopenfilename(title="Selecionar VOD — TUTUCO CLIP MINER", filetypes=[
    ("Vídeos", "*.mp4 *.mkv *.mov *.webm *.avi *.m4v *.ts"), ("Todos os arquivos", "*.*")])
window.destroy()
print(path)
