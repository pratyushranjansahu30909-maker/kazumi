import os
import re
from .base_skill import KazumiSkill

class DocumentRAGSkill(KazumiSkill):
    def __init__(self, bot):
        super().__init__(bot)
        self.documents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "documents")
        self.chunks = []
        self.index_documents()

    def get_triggers(self):
        return [
            r"^/rag",
            r"\b(search documents|search my notes|read my notes|search files)\b"
        ]

    def get_help(self):
        return "/rag <query>", "Search local notes and files in the documents/ directory."

    def index_documents(self):
        """Indexes all text/markdown files in the documents/ folder."""
        self.chunks = []
        if not os.path.exists(self.documents_dir):
            try:
                os.makedirs(self.documents_dir)
                # Create a welcome guide document
                welcome_doc = os.path.join(self.documents_dir, "welcome.md")
                with open(welcome_doc, "w", encoding="utf-8") as f:
                    f.write("# Welcome to Kazumi RAG!\n\nThis is a sample note. Place any text or markdown files (.txt, .md) here to allow Kazumi to search them.\n")
            except Exception:
                return

        for root, dirs, files in os.walk(self.documents_dir):
            for file in files:
                if file.endswith((".txt", ".md", ".json", ".log")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        
                        # Chunk content by paragraph or block
                        paragraphs = re.split(r"\n\s*\n", content)
                        for p in paragraphs:
                            p_clean = p.strip()
                            if len(p_clean) > 10:
                                self.chunks.append({
                                    "filename": file,
                                    "text": p_clean
                                })
                    except Exception as e:
                        print(f"[RAG Indexer Warning] Could not index {file}: {e}")

    def search_documents(self, query, top_k=3):
        """Returns the top_k relevant chunks from documents."""
        # Simple TF-IDF/keyword overlap matching
        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        # Remove common short words
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "is", "are", "of", "about"}
        query_words = query_words - stop_words
        
        if not query_words:
            return []

        scored_chunks = []
        for chunk in self.chunks:
            chunk_words = set(re.findall(r"\b\w+\b", chunk["text"].lower()))
            overlap = len(query_words.intersection(chunk_words))
            if overlap > 0:
                scored_chunks.append((overlap, chunk))
        
        # Sort by overlap score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_chunks[:top_k]]

    def handle(self, text, clean_text, valence):
        intent_text = clean_text.lower().strip()
        
        # Re-index on demand
        if intent_text.startswith("/rag index") or intent_text.startswith("/rag reindex"):
            self.index_documents()
            return f"(Kazumi nods happily...) Document index refreshed! Re-indexed {len(self.chunks)} passages from documents directory. 📚"

        # Explicit search query
        query = ""
        if intent_text.startswith("/rag"):
            parts = intent_text.split(" ", 1)
            if len(parts) > 1:
                query = parts[1].strip()
        else:
            # NL search
            search_match = re.search(r"(?:search documents|search my notes|read my notes|search files)\s+(?:for\s+)?(.*)", intent_text)
            if search_match:
                query = search_match.group(1).strip()

        if not query:
            return "(Kazumi looks at you...) Please tell me what query you'd like to search in your documents! 🌸"

        # Run search
        self.index_documents() # Dynamic sync check
        matches = self.search_documents(query)
        if not matches:
            return f"(Kazumi search results...) I couldn't find any relevant notes or files matching '{query}' in my documents folder. 🥺"

        results_str = f"(Kazumi presents some pages from your logs...) I found {len(matches)} matching entries! 📚\n\n"
        for i, match in enumerate(matches, 1):
            results_str += f"**Match {i} (from {match['filename']}):**\n{match['text']}\n\n"
        
        return results_str
