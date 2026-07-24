import sys
import os

# Menambahkan direktori utama ke path Python agar 'backend' bisa diimport
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.main import app
