# main.py
import platform

def main():
    print("Hello from Nuitka!")
    print(f"System: {platform.system()}")
    print(f"Release: {platform.release()}")
    print("If you see this on your VPS, the compilation worked!")

if __name__ == "__main__":
    main()
