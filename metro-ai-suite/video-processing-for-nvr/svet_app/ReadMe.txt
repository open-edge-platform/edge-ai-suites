1 How to compile
  mkdir build
  cd build & cmake .. & make

2 How to run test_config_parser?
  2.1 get help: 
      ./test_config_parser -h
      It will show all command usages.

  2.2 How to load config file?
      It has two method to run the config_parser test
      a. cd build
         ./test_config_parser load ../test/config.txt
      b. cd build 
         ./test_config_parser 
         you will see input indicator: (svet)>>
         type  load ../test/config.txt

  2.3 You can input any operate command
      for example:
          (svet)>> ctrl --cmd=run --time=100
