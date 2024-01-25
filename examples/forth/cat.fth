interrupt intr_enter
    1818 read
    dup 0 = if 1 stop_input ! then
    1717 omit
ei ;

variable stop_input
0 stop_input !
while stop_input @ endwhile