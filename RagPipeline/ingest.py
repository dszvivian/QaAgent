import os
import sys
import argparse
import uuid
import pymupdf
import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Union, Optional, Dict, Any
import chromadb
from chromadb.utils import embedding_functions

class FileFormatNotSupported(Exception):
    """Exception raised when a file format is not supported."""
    pass

def extract_file_content(file_path: str) -> str:
    """Extract content from a file.
    
    Args:
        file_path: Path to the file.
        
    Returns:
        str: The extracted text content.
        
    Raises:
        FileNotFoundError: If the file does not exist.
        FileFormatNotSupported: If the file format is not supported.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Get the file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    # Extract content based on file type
    if ext == ".pdf":
        return extract_pdf_content(file_path)
    elif ext == ".txt":
        return extract_text_content(file_path)
    elif ext == ".xlsx":
        return extract_excel_values(file_path)
    else:
        raise FileFormatNotSupported(f"File format {ext} is not supported. Only .pdf and .txt files are supported.")
    
def extract_excel_values(file_path:str):
    df = pd.read_excel(file_path)
    testscript_values = df['Test Script (Step-by-Step) - Step'].dropna()
    return '/n'.join(testscript_values.astype(str))
    
    
def extract_pdf_content(file_path: str) -> str:
    """Extract content from a PDF file using PyMuPDF.
    
    Args:
        file_path: Path to the PDF file.
        
    Returns:
        str: The extracted text content.
    """
    text = ""
    try:
        # Open the PDF file
        doc = pymupdf.open(file_path)
        
        # Extract text from each page
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += page.get_text()
            
        doc.close()
        return text
    except Exception as e:
        raise RuntimeError(f"Error extracting PDF content: {str(e)}")
    
def extract_text_content(file_path: str) -> str:
    """Extract content from a text file.
    
    Args:
        file_path: Path to the text file.
        
    Returns:
        str: The extracted text content.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        raise RuntimeError(f"Error extracting text content: {str(e)}")
    
def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Split text into chunks using LangChain's RecursiveCharacterTextSplitter.
    
    Args:
        text: The text to split.
        chunk_size: The size of each chunk.
        chunk_overlap: The overlap between chunks.
        
    Returns:
        List[str]: The list of text chunks.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    
    chunks = text_splitter.split_text(text)
    return chunks


def create_embeddings_and_store(chunks: List[str], collection_name: str = None, model_name: str = "all-MiniLM-L6-v2", db_path: str = "./vectordb") -> chromadb.Collection:
    """Create embeddings for text chunks using SentenceTransformer and store them in ChromaDB.
    
    Args:
        chunks: List of text chunks to embed.
        collection_name: Name of the ChromaDB collection to store embeddings in.
        model_name: Name of the SentenceTransformer model to use.
        
    Returns:
        chromadb.Collection: The ChromaDB collection containing the embeddings.
    """
    print(f"Creating embeddings using SentenceTransformer model '{model_name}'...")
    
    # Initialize the embedding function
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    
    # Create the db directory if it doesn't exist
    os.makedirs(db_path, exist_ok=True)
    
    print(f"Using persistent storage in {db_path}")
    
    # Initialize ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=db_path)
    
    # Create or get collection
    if collection_name is None:
        collection_name = f"document_collection_{uuid.uuid4().hex[:8]}"
    
    # Delete if exists and create new collection
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_function
    )
    
    # Generate unique IDs for each chunk
    ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
    
    # Add chunks to collection with metadata
    metadata = [{"chunk_index": i} for i in range(len(chunks))]
    
    # Add documents to the collection with their embeddings
    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadata
    )
    
    print(f"Successfully created embeddings for {len(chunks)} chunks and stored them in collection '{collection_name}'")
    print(f"Using embedding model: {model_name}")
    
    return collection

def load_collection(collection_name: str, model_name: str = "all-MiniLM-L6-v2", db_path: str = "./vectordb") -> chromadb.Collection:
    """Load a previously stored collection from the persistent storage.
    
    Args:
        collection_name: Name of the ChromaDB collection to load.
        model_name: Name of the SentenceTransformer model to use.
        db_path: Path to the directory where the database is stored.
        
    Returns:
        chromadb.Collection: The loaded ChromaDB collection.
        
    Raises:
        ValueError: If the collection does not exist.
    """
    print(f"Loading collection '{collection_name}' from {db_path}...")
    
    # Initialize the embedding function
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    
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
        
        # Get collection info
        count = collection.count()
        print(f"Successfully loaded collection '{collection_name}' with {count} documents")
        return collection
    except Exception as e:
        raise ValueError(f"Failed to load collection '{collection_name}': {str(e)}")

def load_collection(collection_name: str, model_name: str = "all-MiniLM-L6-v2", db_path: str = "./vectordb") -> chromadb.Collection:
    """Load a previously stored collection from the persistent storage.
    
    Args:
        collection_name: Name of the ChromaDB collection to load.
        model_name: Name of the SentenceTransformer model to use.
        db_path: Path to the directory where the database is stored.
        
    Returns:
        chromadb.Collection: The loaded ChromaDB collection.
        
    Raises:
        ValueError: If the collection does not exist.
    """
    print(f"Loading collection '{collection_name}' from {db_path}...")
    
    # Initialize the embedding function
    embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    
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
        
        # Get collection info
        count = collection.count()
        print(f"Successfully loaded collection '{collection_name}' with {count} documents")
        return collection
    except Exception as e:
        raise ValueError(f"Failed to load collection '{collection_name}': {str(e)}")
    
def process_folder_files(folder_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Process all supported files in a folder, extract content, and split into chunks.
    
    Args:
        folder_path: Path to the folder containing files to process.
        chunk_size: The size of each chunk.
        chunk_overlap: The overlap between chunks.
        
    Returns:
        List[str]: The list of all text chunks from all files in the folder.
        
    Raises:
        FileNotFoundError: If the folder does not exist.
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    
    # List to store all chunks from all files
    all_chunks = []
    
    # Get all files in the folder
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    
    if not files:
        print(f"No files found in folder: {folder_path}")
        return all_chunks
    
    print(f"Found {len(files)} files in folder: {folder_path}")
    
    # Process each file
    for file_path in files:
        try:
            # Try to extract content from the file
            print(f"Processing file: {file_path}")
            content = extract_file_content(file_path)
            
            # Split the content into chunks
            file_chunks = split_text_into_chunks(content, chunk_size, chunk_overlap)
            print(f"Extracted {len(file_chunks)} chunks from {file_path}")
            
            # Add the chunks to the list
            all_chunks.extend(file_chunks)
            
        except FileFormatNotSupported:
            print(f"Skipping unsupported file: {file_path}")
        except Exception as e:
            print(f"Error processing file {file_path}: {str(e)}")
    
    print(f"Total chunks extracted from all files: {len(all_chunks)}")
    return all_chunks

def generate_kb(folder_path:str, collection_name:str):
    try:        
        chunks = process_folder_files(folder_path)
        
        # TODO: Extract subfolder name and name it as collection
        
        if chunks:
            print(f"First chunk preview: {chunks[0][:100]}...")
            print(f"Last chunk preview: {chunks[-1][:100]}...")
        
        if chunks:
            collection = create_embeddings_and_store(
                chunks=chunks,
                collection_name=collection_name,
                db_path='./vectordb'
            )
            
            # Verify embeddings by querying
            if collection:
                # Query using the first chunk as an example
                query_results = collection.query(
                    query_texts=[chunks[0][:100]],
                    n_results=2
                )
                print(f"Query returned {len(query_results['ids'][0])} results")
                print("Query successful!")
            
            return {
                "chunks": chunks,
                "collection": collection
            }
        
        return {"chunks": chunks}
        
    except FileFormatNotSupported as e:
        print(f"Error: {str(e)}")
        return None
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
def main():
    generate_kb(folder_path="./knowledge_base/Amazon",collection_name="Amazon")
    generate_kb(folder_path="./knowledge_base/Udemy",collection_name="Udemy")
    
if __name__ == "__main__":
    main()
