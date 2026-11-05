import os
import pathspec
from assistant.repo.detector import RepositoryDetector


class FileFilter:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        
        # Hardcoded directories we ALWAYS want to ignore
        self.default_ignores = [
            ".git", "__pycache__", "venv", ".venv", "node_modules", 
            "dist", "build", "coverage", ".pytest_cache", "Qwen 2.5", "models"
        ]
        
        # Binary or non-text files we should never try to read
        self.ignore_extensions = [
            ".pyc", ".pyd", ".exe", ".dll", ".so", ".jpg", ".png", 
            ".mp4", ".pdf", ".zip", ".tar", ".gz", ".gguf",
            ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".parquet"
        ]
        
        self.max_file_size_bytes = 1 * 1024 * 1024
        
        self.gitignore_spec = self._load_gitignore()

    def _load_gitignore(self):
        """Loads the .gitignore file and parses it so we can respect its rules."""
        gitignore_path = os.path.join(self.root_dir, ".gitignore")
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r", encoding="utf-8") as f:
                return pathspec.PathSpec.from_lines('gitwildmatch', f)
        return None

    def should_ignore(self, file_path: str) -> bool:
        """Returns True if the file should be ignored, False if it is safe to read."""
        rel_path = os.path.relpath(file_path, self.root_dir)
        
        # Check default ignore folders
        parts = rel_path.replace("\\", "/").split("/")
        if any(part in self.default_ignores for part in parts):
            return True
            
        # Check binary/model extensions
        _, ext = os.path.splitext(file_path)
        if ext.lower() in self.ignore_extensions:
            return True
            
        # Respect .gitignore rules
        if self.gitignore_spec and self.gitignore_spec.match_file(rel_path):
            return True
        # 4. Skip files larger than 1 MB (protects against huge data/bundle files)
        if os.path.isfile(file_path):
            try:
                if os.path.getsize(file_path) > self.max_file_size_bytes:
                    return True
            except OSError:
                return True
            
        return False

class ProjectScanner:
    def __init__(self, start_path: str = ".", root_dir: str = None):
        self.detector = RepositoryDetector(start_path)
        self.project_info = self.detector.get_project_metadata()
        if root_dir:
            self.root_dir = os.path.abspath(root_dir)
            self.project_info["root_path"] = self.root_dir
            self.project_info["project_name"] = os.path.basename(self.root_dir)
        else:
            self.root_dir = self.project_info["root_path"]
        
        self.file_filter = FileFilter(self.root_dir) 

    def get_file_metadata(self, file_path: str) -> dict:
        """Collects lightweight metadata for a single file."""
        stats = os.stat(file_path) 
        _, ext = os.path.splitext(file_path)
        
        lang_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".html": "HTML", ".css": "CSS", ".md": "Markdown",
            ".json": "JSON", ".yaml": "YAML", ".yml": "YAML",
            ".go": "Go", ".rs": "Rust", ".cpp": "C++", ".c": "C"
        }
        
        return {
            "path": file_path,
            "rel_path": os.path.relpath(file_path, self.root_dir),
            "extension": ext.lower(),
            "size_bytes": stats.st_size,
            "language": lang_map.get(ext.lower(), "Unknown")
        }

    def get_all_files(self) -> list:
        """
        Recursively scans the root directory and returns a list of 
        absolute file paths that are safe to read.
        """
        valid_files = []
        
        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            valid_dirnames = []
            for d in dirnames:
                full_dir_path = os.path.join(dirpath, d)
                if not self.file_filter.should_ignore(full_dir_path): 
                    valid_dirnames.append(d)
                    
            dirnames[:] = valid_dirnames
            
            for file in filenames:
                full_file_path = os.path.join(dirpath, file)
                if not self.file_filter.should_ignore(full_file_path):
                    valid_files.append(full_file_path)
                    
        return valid_files

    def scan(self) -> dict:
        """
        Scans the project and returns a dictionary containing 
        project metadata and a list of all valid files with their metadata.
        """
        valid_files = self.get_all_files()
        
        files_metadata = []
        for f in valid_files:
            files_metadata.append(self.get_file_metadata(f))
            
        return {
            "project": self.project_info,
            "files": files_metadata,
            "total_files": len(valid_files)
        }
