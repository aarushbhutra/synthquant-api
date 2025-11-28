# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# We add --no-cache-dir to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the working directory contents into the container at /app
COPY . .

# Expose the port that Uvicorn will run on
EXPOSE 8000

# Run uvicorn when the container launches
# host 0.0.0.0 is required for Docker containers to be accessible
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]