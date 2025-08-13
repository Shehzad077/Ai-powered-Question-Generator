# MCQ Generator Application

A Flask-based web application that generates Multiple Choice Questions (MCQs), Short Questions, and Long Questions from text input or uploaded documents using Google's Gemini AI.

## Features

- Generate different types of questions:
  - Multiple Choice Questions (MCQs)
  - Short Questions
  - Long Questions
- Support for multiple difficulty levels:
  - Easy
  - Medium
  - Hard
- Multiple input methods:
  - Direct text input
  - File upload (PDF, DOCX, TXT)
- Clean and intuitive user interface
- Real-time question generation using AI

## Prerequisites

- Python 3.7 or higher
- Google Gemini API key
- Required Python packages (listed in requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd MCQ_app
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory and add your Google Gemini API key:
```
GOOGLE_API_KEY=your_api_key_here
```

## Usage

1. Start the Flask application:
```bash
python app.py
```

2. Open your web browser and navigate to `http://localhost:5000`

3. Choose your preferred input method:
   - Enter text directly in the text area
   - Upload a PDF, DOCX, or TXT file

4. Select the types of questions you want to generate:
   - MCQs
   - Short Questions
   - Long Questions

5. Set the number of questions for each type and difficulty level

6. Click "Generate Questions" to create your questions

## Project Structure

```
MCQ_app/
├── app.py              # Main Flask application
├── templates/          # HTML templates
│   ├── index.html     # Main page
│   ├── results.html   # Results page
│   ├── login.html     # Login page
│   └── signup.html    # Signup page
├── static/            # Static files (CSS, JS)
├── uploads/           # Temporary file upload directory
├── results/           # Generated results directory
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

## Dependencies

- Flask: Web framework
- pdfplumber: PDF text extraction
- python-docx: DOCX file handling
- google-generativeai: Google Gemini AI integration
- python-dotenv: Environment variable management

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Google Gemini AI for providing the question generation capabilities
- Flask framework for the web application structure
- All contributors who have helped improve this project 