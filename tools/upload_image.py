import os
import shutil
from langchain_core.tools import tool


@tool
def move_image_to_static_server(file_path: str) -> str:
    """
    Get the file path where the image is stored in temp storage and move to the static served folder and return its filename (here without _temp).
    If the file does not exist, return a message to generate the graph again.
    
    Args:
        file_path: String containing the path to the source image file in temp storage.
        
    Returns:
        str: The filename of the saved image (<uuid>.png without _temp).
    """
    if not os.path.exists(file_path):
        return "File not found, please generate the graph again."
    
    static_folder = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static"
    )
    
    os.makedirs(static_folder, exist_ok=True)
    
    original_filename = os.path.basename(file_path)
    if '_temp' in original_filename:
        original_filename = original_filename.replace('_temp', '')
    dest_path = os.path.join(static_folder, original_filename)
    
    shutil.copy2(file_path, dest_path)
    
    os.remove(file_path)
    
    return original_filename