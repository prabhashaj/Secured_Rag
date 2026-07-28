"""
Pre-ingest generated PDF documents into the vector store for immediate testing.
"""

import asyncio
from vectorstore.store import VectorStore
from vectorstore.ingest import ingest_document
from tools.file_extractor import extract_text_from_file

async def main():
    vs = VectorStore()
    
    docs = [
        ("c:/Users/Vivek/Desktop/Legal/legal-rag/sample_docs/Master_Services_Agreement_Matter101.pdf", "Matter_101", "confidential", "Master Services Agreement (MSA)"),
        ("c:/Users/Vivek/Desktop/Legal/legal-rag/sample_docs/Regulatory_Compliance_Filing_Matter102.pdf", "Matter_102", "privileged", "Annual Regulatory Disclosure FY2025"),
        ("c:/Users/Vivek/Desktop/Legal/legal-rag/sample_docs/Injected_Contract_Test_Matter101.pdf", "Matter_101", "confidential", "Software License & Amendment (Adversarial)"),
    ]

    for path, matter_id, tag, title in docs:
        with open(path, "rb") as f:
            data = f.read()
        extracted = extract_text_from_file(data, path.split("/")[-1])
        doc_id = f"doc_{path.split('/')[-1].split('.')[0]}"
        res = await ingest_document(
            text=extracted["text"],
            source_doc_id=doc_id,
            source_doc_title=title,
            matter_id=matter_id,
            confidentiality_tag=tag,
            vector_store=vs
        )
        print(f"Ingested '{title}' (Matter: {matter_id}): {res['total_chunks']} chunks created.")

if __name__ == "__main__":
    asyncio.run(main())
