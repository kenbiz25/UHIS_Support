
# jobs/reindex_kb.py
import sys
# KB filenames/parse errors can contain characters the Windows console (cp1252)
# can't print; this crashed the reindex job mid-run rather than just logging and moving on.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.indexing.pipeline import IndexingPipeline
from config.settings import settings

if __name__ == "__main__":
    # Reindex the configured KB directory (or explicit 'kb' folder)
    indexer = IndexingPipeline(kb_dir="kb")
    total = indexer.reindex_all()
    print(f"Reindexed chunks: {total} (namespace={settings.KB_NAMESPACE}, dim depends on {settings.EMBED_MODEL})")
