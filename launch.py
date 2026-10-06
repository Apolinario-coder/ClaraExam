import sys

if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        from clara.smoke import main
    else:
        from clara.app import main
    main()
