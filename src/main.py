from tools.filesystem_manager import read_file,read_multiple_files,directory_tree,search_files_tool,list_allowed_directories
from tools.stata_interpreter import stata_interpreter
import asyncio

def main():
   paths=r"D:\projects\cuine\src\layouts\Layout.astro"
   log_output = asyncio.run(list_allowed_directories.ainvoke({}))
   print(log_output)
   
if __name__ == "__main__":
   main()
   #path=r"D:\projects\cuine\src\layouts\Layout.astro"
   #result=read_file(path)
   #print(result)