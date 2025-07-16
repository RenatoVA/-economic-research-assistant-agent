import subprocess
from langchain_core.tools import tool
from schema import Stata_interpreter_schema
import os
import asyncio

stata_path = r"C:\Program Files\Stata17\StataMP-64.exe"
do_file = r"D:\projects\test\test_script.do"

@tool("stata_interpreter_tool", args_schema=Stata_interpreter_schema)
async def stata_interpreter(file_path: str) -> str:
    """Execute stata code and return the output"""
    working_dir = os.path.dirname(file_path)
    log_file = os.path.splitext(os.path.basename(file_path))[0] + ".log"
    log_path = os.path.join(working_dir, log_file)

    # Use asyncio.create_subprocess_exec for async execution
    process = await asyncio.create_subprocess_exec(
        stata_path,
        "/e",
        "/b",
        "do",
        file_path,
        cwd=working_dir,
        creationflags=subprocess.CREATE_NO_WINDOW,  # Mantén esto si no quieres ventana
        stdout=subprocess.PIPE,  # Captura la salida estándar
        stderr=subprocess.PIPE,  # Captura errores estándar
    )

    # Wait for the process to complete
    stdout, stderr = await process.communicate()

    # Check for errors
    if process.returncode != 0:
        error_message = f"Stata execution failed with return code {process.returncode}.  Stderr: {stderr.decode(errors='ignore')}"
        print(error_message) #Important, the program will crash without this
        # Consider logging the error or raising an exception
        return error_message  # Or raise an exception

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as file:
            log_content = file.read()
    except Exception as e:
        log_content = f"Error reading log file: {e}"

    return log_content