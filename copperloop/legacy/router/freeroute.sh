#!/bin/zsh
# usage: freeroute.sh in.dsn out.ses passes log
S=$ROUTE_WORK
mkdir -p $S/frhome
exec /Library/Java/JavaVirtualMachines/jdk-25.jdk/Contents/Home/bin/java -Xss16m -Djava.awt.headless=true -Duser.home=$S/frhome -jar $FREEROUTING_JAR --gui.enabled=false --router.fanout.enabled=false --router.plane_as_obstacle=false --router.conduction_is_obstacle=false --router.automatic_neckdown=false --router.autorouter.max_passes="$3" -mt 8 -de "$1" -do "$2" > "$4" 2>&1
