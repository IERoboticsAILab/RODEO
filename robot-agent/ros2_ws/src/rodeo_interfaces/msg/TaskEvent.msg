# Something that happened during a task, on /rodeo/events in the proof bag.
string ARRIVE=arrive      # reached `place`
string DEPART=depart      # left `place`
string SAY=say            # spoke `text`
string CONFIRM=confirm    # `actor` confirmed (e.g. the recipient confirmed receipt)
string NOTE=note          # anything else, in `text`

builtin_interfaces/Time stamp
string type
string place              # place id from services.yaml, "" if not at a place
string text
string actor              # who confirmed, for CONFIRM
