import os
from pathlib import Path

class RepositoryDetector:
    def __init__(self, start_path: str = "."):
        self.start_path = os.path.abspath(start_path)
        self.project_indicators = [
            ".git", 
            "package.json", 
            "pyproject.toml", 
            "requirements.txt", 
            "Cargo.toml", 
            "go.mod",
            "CMakeLists.txt"
        ]

    def find_project_root(self) -> str:
        """
        Traverses upward from the start_path to find the outermost project root.
        Returns the path to the outermost root directory, or the start_path if no root is found.
        """
        current_path = Path(self.start_path)
        outermost_root = None
        
        while current_path != current_path.parent: 
            for indicator in self.project_indicators:
                if (current_path / indicator).exists():
                    outermost_root = str(current_path)
                    break 
            
            current_path = current_path.parent
        
        return outermost_root if outermost_root else self.start_path


    def get_project_metadata(self) -> dict:
        """
        Gathers basic information about the detected repository.
        """
        root = self.find_project_root()
        is_git = os.path.isdir(os.path.join(root, ".git"))
        project_name = os.path.basename(root)

        return {
            "project_name": project_name,
            "root_path": root,
            "is_git_repo": is_git
        }
