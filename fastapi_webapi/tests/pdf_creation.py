import fitz

# Define HTML content and optional CSS styling
html_content = """
<h1>Hello from PyMuPDF Story</h1>
<p>This text is automatically styled, broken into lines, and flowed across pages!</p>
"""

# Set up page dimensions (A4 size) and content margins
mediabox = fitz.paper_rect("A4")
rect = mediabox + (36, 36, -36, -36)  # 0.5 inch margins

# Create the Story and DocumentWriter objects
story = fitz.Story(html=html_content)
writer = fitz.DocumentWriter("output.pdf")

# Render the story into the PDF pages
more = 1
while more:
    device = writer.begin_page(mediabox)
    more, _ = story.place(rect)
    story.draw(device)
    writer.end_page()

writer.close()
