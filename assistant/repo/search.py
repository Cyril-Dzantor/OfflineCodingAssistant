import os
import re
from assistant.repo.scanner import ProjectScanner

class SearchEngine:
    def __init__(self, scanner: ProjectScanner):
        self.scanner = scanner

    def search(self, query: str, is_regex: bool = False, case_sensitive: bool = False) -> list:
        """
        Searches through all valid project files for the query.
        Returns a list of dictionaries containing the file path, line number, and line content.
        """
        results = []
        files_to_search = self.scanner.get_all_files()
        
        # Compile the regex pattern if needed, for faster searching
        flags = 0 if case_sensitive else re.IGNORECASE
        if is_regex:
            pattern = re.compile(query, flags)
        else:
            # Escape the query so special characters aren't treated as regex
            pattern = re.compile(re.escape(query), flags)

        for file_path in files_to_search:
            try:
                # Open the file safely. Ignore decoding errors for weirdly formatted files.
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        
                        if pattern.search(line):
                            results.append({
                                "file": file_path,
                                "line_num": line_num,
                                "content": line.strip()
                            })
                            
            except Exception as e:
                # If we absolutely cannot read the file (e.g., permissions issue), just skip it
                pass

        return results
