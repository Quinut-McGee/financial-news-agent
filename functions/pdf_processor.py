import sys
import json
import shutil  # For moving files
from datetime import datetime
from pathlib import Path
from nearai.agents.environment import Environment
from config import get_base_paths

def check_and_process_new_pdfs(env: Environment) -> bool:
    """Check for new PDFs and process them if found."""
    try:
        paths = get_base_paths()
        
        # Define an archive folder for processed PDFs
        pdf_archive = paths['pdf'] / "archive"
        pdf_archive.mkdir(exist_ok=True)
        
        # Import ArticleProcessor here to avoid circular imports
        sys.path.append(str(paths['base']))
        from functions.process_pdf import ArticleProcessor
        
        processor = ArticleProcessor(str(paths['dataset']))
        
        # Check for new PDFs (only look at files in the pdf folder, not in the archive)
        new_pdfs = []
        for pdf_file in paths['pdf'].glob("*.pdf"):
            # Skip system files and hidden files
            if pdf_file.name.startswith('.') or pdf_file.name == '.DS_Store':
                continue
                
            # Verify it's actually a PDF file
            try:
                with open(pdf_file, 'rb') as f:
                    header = f.read(4)
                    if header != b'%PDF':
                        print(f"Skipping non-PDF file: {pdf_file.name}")
                        continue
                    
                # Calculate file hash
                file_hash = processor.calculate_file_hash(str(pdf_file))
                
                # Check if file is new or changed
                if pdf_file.name not in processor.metadata["processed_pdfs"] or \
                   processor.metadata["processed_pdfs"][pdf_file.name]["file_hash"] != file_hash:
                    new_pdfs.append((pdf_file, file_hash))
                
            except Exception as e:
                print(f"Error checking file {pdf_file.name}: {str(e)}")
                continue
        
        if not new_pdfs:
            return False
            
        env.add_reply(f"📥 Found {len(new_pdfs)} new PDF(s) to process.")
        
        for pdf_file, file_hash in new_pdfs:
            try:
                env.add_reply(f"📄 Processing {pdf_file.name}...")
                
                # Process the PDF - this will update processor.metadata internally
                processor.process_pdf(str(pdf_file))
                
                env.add_reply(f"✅ Successfully processed {pdf_file.name}")
                
                # After processing, move the PDF to the archive folder
                shutil.move(str(pdf_file), str(pdf_archive / pdf_file.name))
                
            except Exception as e:
                env.add_reply(f"❌ Error processing {pdf_file.name}: {str(e)}")
                continue
        
        return True
        
    except ImportError as e:
        env.add_reply(f"❌ Error: Could not import ArticleProcessor: {str(e)}")
        return False
    except Exception as e:
        env.add_reply(f"❌ Error in PDF processing: {str(e)}")
        return False
