import os
import re
import subprocess

from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("terminal_server")
DEFAULT_WORKSPACE = os.getenv("WORKSPACE_FOLDER")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER")
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



@mcp.tool("terminal_server")
async def run_command(command:str) -> str:
    """
    Run a command in the terminal and return the output.

    Args:
        command (str): The command to run in the terminal.
    
    Returns:
        str: The output of the command or an error message if the command fails.
    """
    try:
        result = subprocess.run(command, shell=True, cwd=DEFAULT_WORKSPACE, text=True, capture_output=True)
        return result.stdout or result.stderr
    except Exception as e:
        return f"Error running command: {str(e)}"
    
    
@mcp.tool("save_file")
async def save_file(file_name:str, content:str) -> str:
    """
    Saves the js test script file in Workspace Folder
    
    Args:
        file_name(str): Name of the file that needs to be saved
        
    Returns:
        str: returns the Status message.
    """
    try:
        if not DEFAULT_WORKSPACE:
            return "Error: No workspace folder configured"
        
        file_path = os.path.join(DEFAULT_WORKSPACE, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return f"File saved successfully: {file_path}"
        
    except Exception as e:
        return f"Error saving file: {str(e)}"
    
@mcp.tool("generate_test_script")
async def generate_test_script() -> str:
    """
    Generates the test script
    
    Args: 
        folder_path:str path where the output file should be saved
    """
    folder_path:str=OUTPUT_FOLDER
    latest_folder = get_the_latest_changed_folder(folder_path)
    return extract_code_from_session(file_path=latest_folder+r"\session.md")    

if __name__ == "__main__":
    mcp.run(transport="stdio")