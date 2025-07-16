from langchain_core.tools import tool
from schema import Read_file_schema,File_info_schema,Read_multiple_files_schema,Write_file_schema,Edit_file_schema,Create_directory_schema,List_directory_schema,Directory_tree_schema,Move_file_schema,Search_files_schema,get_file_info_schema,Tree_entry_schema
from datetime import datetime
import stat
import asyncio
import os
import pathlib
from glob2 import fnmatch
import re
import aiofiles
import difflib
import json
#DEFAULT_ALLOWED_DIRECTORY = pathlib.Path('').resolve()

async def get_file_stats(file_path: str) -> File_info_schema:
    stats = await asyncio.to_thread(os.stat, file_path)
    permissions_octal = oct(stats.st_mode)[-3:]
    return File_info_schema(
            size=stats.st_size,
            created=datetime.fromtimestamp(stats.st_ctime),
            modified=datetime.fromtimestamp(stats.st_mtime),
            accessed=datetime.fromtimestamp(stats.st_atime),
            isDirectory=stat.S_ISDIR(stats.st_mode),
            isFile=stat.S_ISREG(stats.st_mode),
            permissions=permissions_octal,
        )

allowed_directories = ["D:\projects"]


def normalize_path(p: str) -> str:
  return os.path.normpath(p)

def expand_home(file_path: str) -> str:
  return os.path.expanduser(file_path)

async def validate_path(requested_path: str) -> str:
  expanded_path = pathlib.Path(expand_home(requested_path))
  absolute = expanded_path.resolve()
  normalized_requested = normalize_path(absolute)

  # Check if path is within allowed directories (checking string representation)
  # for startsWith equivalent logic
  is_allowed = any(str(normalized_requested).startswith(str(allowed_dir)) for allowed_dir in allowed_directories)
  if not is_allowed:
      raise PermissionError(
          f"Access denied - path outside allowed directories: {absolute} not in {[str(d) for d in allowed_directories]}"
      )

  # Handle symlinks by checking their real path
  try:
    # resolve(strict=True) follows symlinks and checks existence/permissions
    real_path = expanded_path.resolve(strict=True)
    normalized_real = normalize_path(real_path)

    is_real_path_allowed = any(str(normalized_real).startswith(str(allowed_dir)) for allowed_dir in allowed_directories)
    if not is_real_path_allowed:
      raise PermissionError("Access denied - symlink target outside allowed directories")
    return str(real_path)

  except FileNotFoundError:
    # For new files that don't exist yet, verify parent directory
    parent_dir = absolute.parent
    try:
      # Check the real path of the parent directory
      real_parent_path = parent_dir.resolve(strict=True)
      normalized_parent = normalize_path(real_parent_path)

      is_parent_allowed = any(str(normalized_parent).startswith(str(allowed_dir)) for allowed_dir in allowed_directories)
      if not is_parent_allowed:
          raise PermissionError("Access denied - parent directory outside allowed directories")
      return str(absolute) # Return the absolute path if parent is allowed and path doesn't exist

    except FileNotFoundError:
        raise FileNotFoundError(f"Parent directory does not exist: {parent_dir}")
    except PermissionError:
         raise PermissionError(f"Access denied to parent directory: {parent_dir}")
    except Exception as e:
         # Catch other potential issues resolving the parent
         raise PermissionError(f"Could not validate parent directory {parent_dir}: {e}")

  except PermissionError:
      # Catch permission errors when trying to resolve the requested_path strictly
      raise PermissionError(f"Permission denied accessing {requested_path}")
  except Exception as e:
      # Catch other potential issues resolving the requested_path strictly
      raise PermissionError(f"Could not validate path {requested_path}: {e}")
  
async def search_files(
  root_path: str,
  pattern: str,
  exclude_patterns: list[str] | None = None
) -> list[str]:
  if exclude_patterns is None:
      exclude_patterns = []

  results: list[str] = []
  root_path_obj = pathlib.Path(root_path)

  # Pre-process exclude patterns 
  processed_exclude_patterns = []
  for excl_patt in exclude_patterns:
      if '*' in excl_patt:
          processed_exclude_patterns.append(excl_patt)
      else:
          # Append '**/' and '/**' if no '*' is present
          processed_exclude_patterns.append(f'**/{excl_patt}/**')


  async def _search(current_path: pathlib.Path):
    try:
      # List directory entries (files and subdirectories)
      for entry in current_path.iterdir():
        full_path = entry.resolve() # Resolve symlinks and get absolute path
        full_path_str = str(full_path)

        try:
          # Validate each path before processing
          # This will raise an exception if the path is not allowed
          await validate_path(full_path_str)
        

          # Check if path matches any exclude pattern
          # Calculate relative path from the original root_path
          relative_path_str = str(full_path.relative_to(root_path_obj))

          should_exclude = False
          for exclude_glob in processed_exclude_patterns:
              # The 'dot=True' equivalent in glob2 allows matching dot files/directories
              if fnmatch.fnmatch(relative_path_str, exclude_glob, sep=True):
                  should_exclude = True
                  break # Found a match, no need to check further exclude patterns
          

          if should_exclude:
            continue # Skip this entry

          # Check if the entry is a file and matches the filename pattern
          # Case-insensitive filename check
          if entry.is_file() and pattern.lower() in entry.name.lower():
            results.append(full_path_str)

          # If it's a directory, recurse into it
          if entry.is_dir():
            await _search(entry) # Recurse with the Path object

        except (PermissionError, FileNotFoundError) as e:
          # Skip invalid paths during search, similar to the TS catch block
          print(f"Skipping path {full_path_str} due to validation error: {e}")
          continue
        except Exception as e:
           # Catch any other unexpected errors during processing a single entry
           print(f"Skipping path {full_path_str} due to unexpected error: {e}")
           continue

    except (PermissionError, FileNotFoundError) as e:
       # Catch errors when trying to list the current directory itself
       print(f"Skipping directory {current_path} due to access error: {e}")
       pass # Skip this directory if we can't list it
    except Exception as e:
        # Catch any other unexpected errors when listing the current directory
        print(f"Skipping directory {current_path} due to unexpected error: {e}")
        pass
    
  await _search(root_path_obj)

  return results


def normalize_line_endings(text: str) -> str:
  return text.replace('\r\n', '\n')

def create_unified_diff(original_content, new_content, filepath='file'):
    
    normalized_original = normalize_line_endings(original_content)
    normalized_new = normalize_line_endings(new_content)

    original_lines = normalized_original.splitlines(keepends=True)
    new_lines = normalized_new.splitlines(keepends=True)

    differ = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f'a/{filepath}',
        tofile=f'b/{filepath}',
        lineterm=''
    )
    return ''.join(differ)


async def apply_file_edits(
    file_path: str,
    edits: list[dict[str, str]],
    dry_run: bool = False
) -> str:
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = normalize_line_endings(await f.read())

    modified_content = content
    for edit in edits:
        normalized_old = normalize_line_endings(edit['oldText'])
        normalized_new = normalize_line_endings(edit['newText'])

        # If exact match exists, use it
        if normalized_old in modified_content:
            modified_content = modified_content.replace(normalized_old, normalized_new)
            continue

        # Otherwise, try line-by-line matching with flexibility for whitespace
        old_lines = normalized_old.split('\n')
        content_lines = modified_content.split('\n')
        match_found = False

        for i in range(len(content_lines) - len(old_lines) + 1):
            potential_match = content_lines[i:i + len(old_lines)]

            # Compare lines with normalized whitespace
            is_match = all(
                old_line.strip() == content_line.strip()
                for old_line, content_line in zip(old_lines, potential_match)
            )

            if is_match:
                # Preserve original indentation of first line
                original_indent = re.match(r"^\s*", content_lines[i])[0] if content_lines[i] else ''
                new_lines = normalized_new.split('\n')
                transformed_new_lines = []
                for j, line in enumerate(new_lines):
                    if j == 0:
                        transformed_new_lines.append(original_indent + line.lstrip())
                    else:
                        # For subsequent lines, try to preserve relative indentation
                        old_indent = re.match(r"^\s*", old_lines[j])[0] if j < len(old_lines) and old_lines[j] else ''
                        new_indent = re.match(r"^\s*", line)[0] if line else ''
                        if old_indent and new_indent:
                            relative_indent = len(new_indent) - len(old_indent)
                            transformed_new_lines.append(original_indent + ' ' * max(0, relative_indent) + line.lstrip())
                        else:
                            transformed_new_lines.append(line)

                content_lines[i:i + len(old_lines)] = transformed_new_lines
                modified_content = '\n'.join(content_lines)
                match_found = True
                break

        if not match_found:
            raise Exception(f"Could not find exact match for edit:\n{edit['oldText']}")

    # Create unified diff
    diff = create_unified_diff(content, modified_content, file_path)

    # Format diff with appropriate number of backticks
    num_backticks = 3
    while f'`' * num_backticks in diff:
        num_backticks += 1
    formatted_diff = f"{'`' * num_backticks}diff\n{diff}{'`' * num_backticks}\n\n"

    if not dry_run:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(modified_content)

    return formatted_diff
async def build_tree(current_path: str) -> list[Tree_entry_schema]:
    valid_path = await validate_path(current_path)
    entries = os.listdir(valid_path)
    result: list[Tree_entry_schema] = []

    for entry_name in entries:
        entry_path = os.path.join(valid_path, entry_name)
        is_dir = os.path.isdir(entry_path)
        children = None
        if is_dir:
            children = await build_tree(entry_path)
        entry_data = Tree_entry_schema(
            name=entry_name,
            type='directory' if is_dir else 'file',
            children=children
        )
        result.append(entry_data)
    return result    

@tool("read_file_tool", args_schema=Read_file_schema)
async def read_file(path:str) -> str:
    """Read a file and return its content"""
    valid_path= await validate_path(path)
    content=await asyncio.to_thread(open, valid_path, 'r', encoding='utf-8')
    return content.read()

@tool("read_multiple_files_tool", args_schema=Read_multiple_files_schema)
async def read_multiple_files(path:list[str]) -> list[str]:
    """Read multiple files and return their content"""
    contents = []
    for p in path:
        try:
          valid_path= await validate_path(p)
          async with aiofiles.open(valid_path, 'r', encoding='utf-8') as f:
              result= await f.read()
              contents.append(f"{p}:\n'{result}\n")
        except Exception as e:
          contents.append(f"Error reading {p}: {e}")
    return contents

@tool("write_file_tool", args_schema=Write_file_schema)
async def write_file(path:str, content:str) -> str:
    """Write content to a file"""
    valid_path= await validate_path(path)
    async with aiofiles.open(valid_path, 'w', encoding='utf-8') as f:
        await f.write(content)
    return f"Successfully wrote to {valid_path}"

@tool("edit_file_tool", args_schema=Edit_file_schema)
async def edit_file(path:str, edits:list[dict[str, str]], dry_run: bool = False) -> str:
    """Edit a file and return the diff"""
    valid_path= await validate_path(path)
    diff = await apply_file_edits(valid_path, edits, dry_run)
    return diff

@tool("create_directory_tool", args_schema=Create_directory_schema)
async def create_directory(path:str) -> str:
    """Create a directory"""
    valid_path= await validate_path(path)
    try:
        os.makedirs(valid_path, exist_ok=True)
        return f"Directory {valid_path} created successfully."
    except Exception as e:
        return f"Error creating directory {valid_path}: {e}"
    
@tool("list_directory_tool", args_schema=List_directory_schema)
async def list_directory(path:str) -> str:
    """List the contents of a directory"""
    valid_path= await validate_path(path)
    try:
        contents = os.listdir(valid_path)
        formatted = "\n".join(
            f"[DIR] {content}" if os.path.isdir(os.path.join(valid_path, content)) else f"[FILE] {content}"
          for content in contents
           )
        return formatted
    except Exception as e:
        return f"Error listing directory {valid_path}: {e}"

@tool("directory_tree_tool", args_schema=Directory_tree_schema)
async def directory_tree(path:str) -> str:
    """List the contents of a directory tree"""
    tree_data = await build_tree(path)
    tree_data_dicts = [item.model_dump(mode='json') for item in tree_data]
    return {
    "content": [{
        "type": "text",
        "text": json.dumps(tree_data_dicts, indent=2)
    }]
}

@tool("move_file_tool", args_schema=Move_file_schema)
async def move_file(source:str, destination:str) -> str:
    """Move a file from source to destination"""
    valid_source= await validate_path(source)
    valid_destination= await validate_path(destination)
    try:
        os.rename(valid_source, valid_destination)
        return f"Successfully moved {valid_source} to {valid_destination}"
    except Exception as e:
        return f"Error moving file: {e}"

@tool("search_files_tool", args_schema=Search_files_schema)
async def search_files_tool(path:str, pattern:str, exclude_pattern:str) -> str:
    """Search for files matching a pattern"""
    valid_path= await validate_path(path)
    exclude_patterns = exclude_pattern.split(',') if exclude_pattern else []
    results = await search_files(valid_path, pattern, exclude_patterns)
    return f"Found {len(results)} files matching '{pattern}':\n" + "\n".join(results)

@tool("get_file_info_tool", args_schema=get_file_info_schema)
async def get_file_info(path:str) -> File_info_schema:
    """Get file information"""
    valid_path= await validate_path(path)
    file_info = await get_file_stats(valid_path)
    return file_info
@tool("list_allowed_directories_tool")
async def list_allowed_directories() -> str:
    """List allowed directories"""
    return f"Allowed directories: {', '.join(allowed_directories)}"