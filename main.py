#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "openpyxl",
#     "beautifulsoup4",
#     "python-dateutil",
#     "pyzotero",
#     "arxiv",
#     "requests",
#     "pyperclip",
#     "pyTelegramBotAPI",
# ]
# ///

import argparse
import sys
import os

from zotero_report_generator import generate_html
from paper_analyzer import analyze_papers

def main():
    banner = "\033[95m" + r"""
 _      _ _   _____                               _      
| |    (_) | |  __ \                             | |     
| |     _| |_| |__) |___  ___  ___  __ _ _ __ ___| |__   
| |    | | __|  _  // _ \/ __|/ _ \/ _` | '__/ __| '_ \  
| |____| | |_| | \ \  __/\__ \  __/ (_| | | | (__| | | | 
|______|_|\__|_|  \_\___||___/\___|\__,_|_|  \___|_| |_| 
""" + "\033[0m"
    print(banner)

    parser = argparse.ArgumentParser(
        description="Academic Literature Analysis & Zotero PDF Compiler Utility"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")
    
    # Subcommand 'generate'
    gen_parser = subparsers.add_parser(
        "generate", 
        help="Convert raw bibliography JSON export to styled Zotero HTML report"
    )
    gen_parser.add_argument(
        "--json", 
        default="bibliography.json", 
        help="Path to Zotero JSON export file (default: bibliography.json)"
    )
    gen_parser.add_argument(
        "--html", 
        default="bibliography.html", 
        help="Path to output HTML report file (default: bibliography.html)"
    )
    
    # Subcommand 'analyze'
    ana_parser = subparsers.add_parser(
        "analyze", 
        help="Query academic APIs, compare authors, and compile LaTeX report to PDF"
    )
    ana_parser.add_argument(
        "--html", 
        default="bibliography.html", 
        help="Path to input HTML report file (default: bibliography.html)"
    )
    ana_parser.add_argument(
        "--tex", 
        default="bibliography.tex", 
        help="Path to output LaTeX TeX file (default: bibliography.tex)"
    )
    ana_parser.add_argument(
        "--excel", 
        default=None, 
        help="Path to top scientists Excel spreadsheet (default: auto-scans directory)"
    )
    ana_parser.add_argument(
        "--template", 
        default=None, 
        help="Path to main LaTeX template file (default: report_template.tex)"
    )
    ana_parser.add_argument(
        "--item-template", 
        default=None, 
        help="Path to LaTeX item template file (default: paper_item_template.tex)"
    )
    
    # Subcommand 'run' (End-to-end pipeline)
    run_parser = subparsers.add_parser(
        "run", 
        help="Run the complete pipeline end-to-end: JSON -> HTML -> TeX & PDF"
    )
    run_parser.add_argument(
        "--json", 
        default="bibliography.json", 
        help="Path to input Zotero JSON export file (default: bibliography.json)"
    )
    run_parser.add_argument(
        "--html", 
        default="bibliography.html", 
        help="Path to intermediate HTML report file (default: bibliography.html)"
    )
    run_parser.add_argument(
        "--tex", 
        default="bibliography.tex", 
        help="Path to output LaTeX TeX file (default: bibliography.tex)"
    )
    run_parser.add_argument(
        "--excel", 
        default=None, 
        help="Path to top scientists Excel spreadsheet (default: auto-scans directory)"
    )
    run_parser.add_argument(
        "--template", 
        default=None, 
        help="Path to main LaTeX template file (default: report_template.tex)"
    )
    run_parser.add_argument(
        "--item-template", 
        default=None, 
        help="Path to LaTeX item template file (default: paper_item_template.tex)"
    )
    run_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove intermediate HTML and TeX files after successful run"
    )
    
    args = parser.parse_args()
    
    try:
        if args.command == "generate":
            success = generate_html(args.json, args.html)
            if not success:
                sys.exit(1)
                
        elif args.command == "analyze":
            success = analyze_papers(
                input_filename=args.html,
                output_filename=args.tex,
                excel_path=args.excel,
                report_template_path=args.template,
                paper_item_template_path=args.item_template
            )
            if not success:
                sys.exit(1)
                
        elif args.command == "run":
            try:
                print(">>> Phase 1/2: Generating HTML Report from Zotero JSON Export...")
                success = generate_html(args.json, args.html)
                if not success:
                    print("Failed at Phase 1: HTML generation.")
                    sys.exit(1)
                    
                print("\n>>> Phase 2/2: Querying APIs and Compiling to PDF...")
                success = analyze_papers(
                    input_filename=args.html,
                    output_filename=args.tex,
                    excel_path=args.excel,
                    report_template_path=args.template,
                    paper_item_template_path=args.item_template
                )
                if not success:
                    print("Failed at Phase 2: Paper analysis and PDF compilation.")
                    sys.exit(1)
            finally:
                if args.clean:
                    print("\n>>> Cleaning up intermediate files...")
                    for fpath in [args.html, args.tex]:
                        if os.path.exists(fpath):
                            try:
                                os.remove(fpath)
                                print(f" Removed: {fpath}")
                            except Exception as e:
                                print(f" Warning: Could not remove {fpath}: {e}")
                            
            print("\n>>> Pipeline execution completed successfully!")
    except KeyboardInterrupt:
        print("\n[!] Execution interrupted by user. Exiting gracefully...")
        # If interrupted during run and clean is specified, clean up
        if args.command == "run" and args.clean:
            print(">>> Cleaning up intermediate files...")
            for fpath in [args.html, args.tex]:
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except:
                        pass
        sys.exit(130)

if __name__ == "__main__":
    main()
