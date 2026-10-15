from .app.main import main

try:
    main()                      # problems and crashes are logged and shown there
except KeyboardInterrupt:
    pass
