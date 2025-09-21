import os
import chromadb
from chromadb.utils import embedding_functions



embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

def query_knowledge_base(query:str,collection_name,db_path:str='./vectordb') -> str:
    print(f"Loading collection '{collection_name}' from {db_path}...")    
    
    # Check if the db path exists
    if not os.path.exists(db_path):
        raise ValueError(f"Database directory '{db_path}' does not exist")
    
    # Initialize ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        # Get the existing collection
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
        
        query_results = collection.query(
                    query_texts=[query],
                    n_results=2
                )
    
        return "/n/n".join(sum(query_results["documents"], []))
        
    except Exception as e:
        raise ValueError(f"Failed to query knowledge base '{collection_name}': {str(e)}")
    
    
if __name__ == "__main__":
    while True:
        qry = input("input: ")
        print(query_knowledge_base(qry,"Amazon"))
        print(f"\n")