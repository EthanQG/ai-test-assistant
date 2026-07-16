import os
import time


class KnowledgeBaseManager:
    def __init__(self):
        self.default_kb_path = "./knowledge/bug_experience.txt"
        self.history_points_dir = "./knowledge/history_points"

    def load_bug_experience(self, file_path: str = None) -> str:
        target_path = file_path or self.default_kb_path

        if not os.path.exists(target_path):
            return ""

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            return content
        except Exception as e:
            return ""

    def load_knowledge(self, file_path: str) -> str:
        return self.load_bug_experience(file_path)

    def save_knowledge(self, content: str, file_path: str = None) -> bool:
        target_path = file_path or self.default_kb_path

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            return False

    def load_history_test_points(self) -> str:
        if not os.path.exists(self.history_points_dir):
            return ""

        history_content = ""
        try:
            for filename in os.listdir(self.history_points_dir):
                if filename.endswith(".md"):
                    filepath = os.path.join(self.history_points_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            lines = f.readlines()[:20]
                            file_content = "".join(lines).strip()
                            if file_content:
                                history_content += f"【历史测试点 - {filename}】\n{file_content}\n\n"
                    except Exception:
                        continue

            return history_content.strip()
        except Exception:
            return ""

    def save_test_points(self, content: str, prd_title: str = "") -> str:
        if not os.path.exists(self.history_points_dir):
            os.makedirs(self.history_points_dir, exist_ok=True)

        if prd_title:
            safe_title = prd_title[:5].strip().replace("/", "_").replace("\\", "_").replace(":", "_")
            safe_title = "".join(c for c in safe_title if c not in ['<', '>', ':', '"', '/', '\\', '|', '?', '*'])
            if not safe_title:
                safe_title = "untitled"
        else:
            safe_title = "untitled"

        timestamp = int(time.time())
        filename = f"{safe_title}_{timestamp}.md"
        filepath = os.path.join(self.history_points_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return filepath
        except Exception as e:
            raise ValueError(f"保存失败: {str(e)}")