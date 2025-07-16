from typing import Any, Literal, NotRequired, Annotated, List,Optional
from pydantic import BaseModel, Field, SerializeAsAny
from datetime import datetime

class Stata_interpreter_schema(BaseModel):
    file_path:str=Field(description="path to the .do file")

class Read_file_schema(BaseModel):
    path:str=Field(description="path to the file to read")

class Read_multiple_files_schema(BaseModel):
    path:List[str]=Field(description="paths to the files to read")

class Write_file_schema(BaseModel):
    path:str=Field(description="path to the file to write")
    content:str=Field(description="content to write to the file")

class Edit_operation(BaseModel):
    old_text:str=Field(description="Text to search for - must match exact")
    new_text:str=Field(description="Text to replace with")

class Edit_file_schema(BaseModel):
    path:str=Field(description="path to the file to edit")
    edits:List[Edit_operation]=Field(description="List of edits to make to the file")
    dry_run: bool = Field(
        default=False,
        description="Preview changes using git-style diff format"
    )

class Create_directory_schema(BaseModel):
    path:str=Field(description="path to the directory to create")

class List_directory_schema(BaseModel):
    path:str=Field(description="path to the directory to list")

class Directory_tree_schema(BaseModel):
    path:str=Field(description="path to the directory to list")

class Move_file_schema(BaseModel):
    source:str=Field(description="path to the source file")
    destination:str=Field(description="path to the destination file")

class Search_files_schema(BaseModel):
    path:str=Field(description="path to the directory to search")
    pattern:str=Field(description="pattern to search for")
    exclude_pattern:str=Field(description="pattern to exclude from search")

class get_file_info_schema(BaseModel):
    path:str=Field(description="path to the file to get info about")

class File_info_schema(BaseModel):
    size: int=Field(description="size of the file in bytes")
    created: datetime = Field(description="creation date of the file")
    modified: datetime = Field(description="last modified date of the file")
    accessed: datetime = Field(description="last accessed date of the file")
    isDirectory: bool= Field(description="True if the path is a directory")
    isFile: bool= Field(description="True if the path is a file")
    permissions: str = Field(description="permissions of the file")
class Tree_entry_schema(BaseModel):
    name: str
    type: Literal['file', 'directory']
    children: Optional[List['Tree_entry_schema']] = None
    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True,
    }