"""
Text chunking for embedding
"""
import re
from typing import List, Tuple
from pathlib import Path

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    Tries to split on paragraph/sentence boundaries.
    """
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Split on double newlines first (paragraphs)
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # If adding this paragraph exceeds chunk size, save current and start new
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Keep overlap from end of previous chunk
            words = current_chunk.split()
            overlap_words = words[-overlap:] if len(words) > overlap else words
            current_chunk = ' '.join(overlap_words) + '\n\n'
        
        current_chunk += para + '\n\n'
    
    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def chunk_file(path: Path) -> List[Tuple[str, int, str]]:
    """
    Chunk a file and return (chunk_text, chunk_index, source_path) tuples.
    """
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return []
    
    chunks = chunk_text(content)
    return [(chunk, i, str(path)) for i, chunk in enumerate(chunks)]

if __name__ == "__main__":
    # Test
    sample = """# Header

This is the first paragraph with some content.

This is the second paragraph. It has more text to demonstrate chunking behavior.

## Another Section

More content here in a different section. This helps test the chunking logic.
"""
    chunks = chunk_text(sample, chunk_size=100)
    print(f"Created {len(chunks)} chunks:")
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({len(c)} chars) ---")
        print(c[:100] + "..." if len(c) > 100 else c)
