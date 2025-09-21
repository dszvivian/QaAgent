import os
import re

PLAYWRIGHT_HEADER = """const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

"""

PLAYWRIGHT_FOOTER = """
    await context.close();
    await browser.close();
})();
"""

def extract_code_from_session(file_path) -> str:
    """
    Extract only the code parts from a session.md file and return as string,
    wrapped in Playwright boilerplate.
    
    Args:
        file_path (str): Path to the session.md file
        
    Returns:
        str: Concatenated code blocks from the session, wrapped in Playwright script
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Pattern to match code blocks within - Code sections
    code_pattern = r'- Code\s*```(?:js|javascript)\s*(.*?)```'
    
    # Find all code blocks
    code_matches = re.findall(code_pattern, content, re.DOTALL)
    
    # Join all code blocks with newlines
    extracted_code = '\n\n'.join(match.strip() for match in code_matches)
    
    # Wrap with Playwright header and footer
    full_script = PLAYWRIGHT_HEADER + extracted_code + PLAYWRIGHT_FOOTER
    
    return full_script

def get_the_latest_changed_folder(folder_path:str):
    try:
        # Get all subdirectories in the root folder
        subfolders = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, f))
        ]
        
        if not subfolders:
            return None
        
        # Find the folder with the latest modification time
        latest_folder = max(subfolders, key=os.path.getmtime)
        return latest_folder
    
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    latest_folder = get_the_latest_changed_folder(folder_path=r".\output")
    print(latest_folder)
    code = extract_code_from_session(file_path=latest_folder+r"\session.md")
    print(code)