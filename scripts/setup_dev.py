#!/usr/bin/env python3

import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlretrieve


def run_command(cmd, cwd=None):
    """Run a command and stream its output"""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
        cwd=cwd
    )

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)


def install_uv():
    """Install uv if not already installed"""
    if subprocess.run(['which', 'uv'], capture_output=True).returncode == 0:
        print("✓ uv already installed")
        return

    print("Installing uv package manager...")

    # Determine platform
    system = platform.system().lower()
    machine = platform.machine()
    if machine == 'x86_64':
        machine = 'amd64'
    elif machine == 'aarch64':
        machine = 'arm64'

    uv_version = "0.1.13"
    platform_name = f"{system}-{machine}"
    url = f"https://github.com/astral-sh/uv/releases/download/{uv_version}/uv-{platform_name}.tar.gz"

    # Download and extract uv
    tmp_file = "/tmp/uv.tar.gz"
    urlretrieve(url, tmp_file)
    os.makedirs("/usr/local/bin", exist_ok=True)
    run_command(f"tar zxf {tmp_file} -C /usr/local/bin")
    os.remove(tmp_file)
    print("✓ uv installed successfully")


def setup_development_env():
    """Set up the development environment"""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Install development dependencies
    print("\nInstalling development dependencies...")
    run_command("uv pip install -e '.[dev]'")
    print("✓ Dependencies installed")

    # Install pre-commit hooks
    print("\nInstalling pre-commit hooks...")
    run_command("pre-commit install")
    print("✓ Pre-commit hooks installed")

    # Create .env file if it doesn't exist
    env_file = project_root / '.env'
    if not env_file.exists():
        print("\nCreating .env file...")
        env_content = """DEBUG=1
SECRET_KEY=development-secret-key
DATABASE_URL=postgres://atria:development@localhost:5432/atria"""
        env_file.write_text(env_content)
        print("✓ .env file created")

    # Start development environment
    print("\nStarting development environment...")
    run_command("docker-compose up -d db")
    print("✓ Database container started")

    # Wait for database to be ready
    print("\nWaiting for database to be ready...")
    time.sleep(5)  # Basic wait, could be improved with proper health check
    print("✓ Database ready")

    # Run migrations
    print("\nRunning migrations...")
    run_command("python manage.py migrate")
    print("✓ Migrations applied")

    # Create superuser if it doesn't exist
    print("\nCreating superuser if it doesn't exist...")
    create_superuser_code = """
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created')
else:
    print('Superuser already exists')
"""
    run_command(f'python manage.py shell -c "{create_superuser_code}"')


def main():
    """Main setup function"""
    try:
        print("Setting up development environment...\n")
        install_uv()
        setup_development_env()
        print("\n✨ Development environment is ready!")
        print("Run 'python manage.py runserver' to start the development server")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error: Command failed with exit code {e.returncode}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
