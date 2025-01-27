from dotenv import load_dotenv
import streamlit as st
import base64
from anthropic import Anthropic
from jinja2 import Template

load_dotenv()
TEMPLATE_STRING = """
{{ introduction }}

{% for section in sections %}
{{ section.text }}{% if section.footnote_numbers %}[^{{ section.footnote_numbers|join('][^') }}]{% endif %}

{% endfor %}

{% for citation in citations %}
[^{{ citation.number }}]: {{ citation.text }} *({{ citation.page_range }})*
{% endfor %}
"""

def pdf_to_base64(pdf_bytes):
    """Convert PDF bytes to base64 string"""
    return base64.b64encode(pdf_bytes).decode('utf-8')

def parse_message_content(message):
    """
    Parses the message content into a structure suitable for the template.
    Returns a dict with introduction and sections, where each section has text and citations.
    """
    parsed_content = {
        'introduction': '',
        'sections': []
    }
    
    current_section = None
    footnote_counter = 1
    all_citations = []
    
    for block in message.content:
        if block.type == 'text':
            # If it's the first block without citations, treat it as introduction
            if not block.citations and not parsed_content['introduction']:
                parsed_content['introduction'] = block.text.strip()
                continue
                
            # Start a new section
            if block.citations or (not block.citations and block.text.strip() in ['However, there is an important exception:', '']):
                # If there's a current section, add it to the list
                if current_section:
                    parsed_content['sections'].append(current_section)
                
                current_section = {
                    'text': block.text.strip(),
                    'citations': [],
                    'footnote_numbers': []
                }
                
                # Add citations if they exist
                if block.citations:
                    for citation in block.citations:
                        current_section['citations'].append({
                            'cited_text': citation.cited_text.strip(),
                            'page_range': f"Pages {citation.start_page_number}-{citation.end_page_number}",
                            'footnote_number': footnote_counter
                        })
                        current_section['footnote_numbers'].append(footnote_counter)
                        all_citations.append({
                            'number': footnote_counter,
                            'text': citation.cited_text.strip(),
                            'page_range': f"Pages {citation.start_page_number}-{citation.end_page_number}"
                        })
                        footnote_counter += 1
    
    # Add the last section if it exists
    if current_section:
        parsed_content['sections'].append(current_section)
    
    parsed_content['citations'] = all_citations
    return parsed_content

def render_message(message):
    """
    Takes a message object and returns rendered markdown using the template
    """
    template = Template(TEMPLATE_STRING)
    parsed_content = parse_message_content(message)
    return template.render(**parsed_content)


def call_anthropic(text, question):
    client = Anthropic()
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": text
                        },
                        "citations": {"enabled": True}
                    },
                    {
                        "type": "text",
                        "text": question
                    }
                ]
            }
        ]
    )
    return response

# Page config
st.set_page_config(
    page_title="Document Q&A",
    page_icon="📚"
)

# Main content
st.title("Document Question & Answer")

st.markdown("""
Upload a PDF document and ask questions about its contents. 
The response will be generated using Claude 3.
""")

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

# Text area for question
question = st.text_area(label="Enter your question about the document:", height=100)

# Submit button
submit = st.button("Submit")

# Create a placeholder for the response
response_placeholder = st.empty()

# Process the form
if submit and uploaded_file is not None and question:
    try:
        # Convert PDF to base64
        pdf_base64 = pdf_to_base64(uploaded_file.getvalue())
        
        # Show loading message
        with response_placeholder:
            st.info("Processing your question...")
            
        # Call Anthropic API
        response = call_anthropic(pdf_base64, question)
        markdown = render_message(response)
        
        # Display the response
        with response_placeholder:
            st.markdown(markdown)

    except Exception as e:
        with response_placeholder:
            st.error(f"An error occurred: {str(e)}")
            
elif submit:
    if not uploaded_file:
        st.warning("Please upload a PDF file.")
    if not question:
        st.warning("Please enter a question.")
