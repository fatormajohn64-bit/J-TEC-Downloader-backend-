import os
import shutil

def remove_temp_folder(folder_path: str):
    """Deletes temporary folder and contained media after client download finishes."""
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path, ignore_errors=True)
      
