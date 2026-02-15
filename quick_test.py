"""Quick test for image generator."""

from image_generator import generate_social_post

print("Generating blockchain post...")
result = generate_social_post(
    article_text="La blockchain transforme le secteur financier mondial",
    image_query="blockchain finance technology",
    output_filename="test_blockchain.png",
)
print(f"SUCCESS: {result}")
