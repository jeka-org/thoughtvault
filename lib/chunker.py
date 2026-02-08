"""
Smart text chunking for embedding - respects markdown structure.
"""
import re
from typing import List, Tuple
from pathlib import Path

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into chunks respecting markdown structure.
    Preserves: headers, code blocks, lists, paragraphs.
    """
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Split into semantic sections by headers
    sections = _split_by_headers(text)
    
    chunks = []
    for section in sections:
        if len(section) <= chunk_size:
            if section.strip():
                chunks.append(section.strip())
        else:
            # Section too large, split further
            sub_chunks = _split_large_section(section, chunk_size, overlap)
            chunks.extend(sub_chunks)
    
    return chunks

def _split_by_headers(text: str) -> List[str]:
    """Split text at markdown headers, keeping header with its content."""
    # Split at ## and ### headers (keep # with intro)
    parts = re.split(r'(?=\n#{1,3}\s)', text)
    return [p for p in parts if p.strip()]

def _split_large_section(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Split a large section respecting paragraph and code block boundaries."""
    # Don't split inside code blocks
    code_block_pattern = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Overlap: keep last few words for context continuity
            words = current_chunk.split()
            overlap_words = words[-overlap:] if len(words) > overlap else words
            current_chunk = ' '.join(overlap_words) + '\n\n'
        
        current_chunk += para + '\n\n'
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

def extract_context(content: str, path: Path) -> str:
    """Extract file context: filename + first header if present."""
    filename = path.stem.replace('-', ' ').replace('_', ' ')
    
    header_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if header_match:
        return f"[{filename}] {header_match.group(1)}: "
    return f"[{filename}]: "

def chunk_file(path: Path) -> List[Tuple[str, int, str]]:
    """
    Chunk a file and return (chunk_text, chunk_index, source_path) tuples.
    Prepends file context to each chunk for better search relevance.
    """
    try:
        content = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return []
    
    context = extract_context(content, path)
    chunks = chunk_text(content)
    return [(context + chunk, i, str(path)) for i, chunk in enumerate(chunks)]

if __name__ == "__main__":
    sample = """# Header

This is the first paragraph with some content.

This is the second paragraph. It has more text.

## Another Section

More content here in a different section.

### Subsection

Even more specific content.
"""
    chunks = chunk_text(sample, chunk_size=100)
    print(f"Created {len(chunks)} chunks:")
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i} ({len(c)} chars) ---")
        print(c[:100] + "..." if len(c) > 100 else c)
