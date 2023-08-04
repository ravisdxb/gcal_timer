# gcal_timer.py
# Google Calendar events with Timer
# ravisdxb@gmail.com

import appdaemon.plugins.hass.hassapi as hass
import sys
sys.path.append('/config/appdaemon/lib')
import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GCalTimer(hass.Hass):
    def initialize(self):
        self.tz_offset=self.get_tz_offset()
        # refresh calendar every x minutes
        interval_minutes=self.args['REFRESH_MINUTES']
        interval_seconds=interval_minutes*60
        now=datetime.datetime.now()
        remaining_minutes=interval_minutes-(now.minute%interval_minutes)
        adjusted=now+datetime.timedelta(minutes=remaining_minutes)
        start=adjusted.replace(second=0,microsecond=0)
        self.run_every(self.auto_update,start,interval_seconds)
        #self.run_hourly(self.hourly_update,datetime.time(0,0,0))
        # refresh calendar when input_boolean is triggered
        self.trigger=self.args['TRIGGER']
        self.listen_state(self.manual_update, self.trigger, new='on')

    # use the timezone info the user to calculate date/time
    def tz_format(self, offset_min):
        tz_str='T00:00:00'
        if offset_min>=0:
            tz_str+='-'
        else:
            tz_str+='+'
        offset_min=abs(offset_min)
        offset_h=int(offset_min/60)
        offset_m=offset_min%60
        tz_str+="%02d:%02d"%(offset_h,offset_m)
        return tz_str

    def auto_update(self, kwargs):
        self.turn_on(self.args['TRIGGER'])

    def manual_update(self, entity, attribute, old, new, kwargs):
        for user in self.args['USERS']:
            self.user=user
            self.get_events(self)
            self.log(f'Google Calendar Updated for {self.user}')
        self.turn_off(self.args['TRIGGER'])

    def get_events(self, kwargs):
        self.token_file='/config/appdaemon/gcal/'+self.user.replace(' ','_')+'_token.json'
        self.creds_file='/config/appdaemon/gcal/'+self.user.replace(' ','_')+'_credentials.json'
        self.html_small_file='/config/www/gcal_timer/'+self.user.replace(' ','_')+'_gcal_timer_small.html'
        self.html_big_file='/config/www/gcal_timer/'+self.user.replace(' ','_')+'_gcal_timer_big.html'
        # from quick start guide
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = None
        if os.path.exists(self.token_file):
            creds=Credentials.from_authorized_user_file(self.token_file,SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())

        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        ev_ctr=0
        ev_html='_'
        tz=self.tz_format(self.tz_offset)
        events_result = service.events().list(calendarId='primary', timeMin=now,
            maxResults=self.args['EVENTS_LIMIT'], singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
        if events:
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                try:
                    loc=event['location']
                except:
                    loc='_NO_LOC_'
                ev_html+="\nev_loc.push('"+loc+"')"
                if len(start)==10:
                    ev_html+="\nev_start.push('"+start+tz+"')"
                    ev_html+="\nev_end.push('"+end+tz+"')"
                    ev_html+="\nev_allday.push('1')"
                else:
                    ev_html+="\nev_start.push('"+start+"')"
                    ev_html+="\nev_end.push('"+end+"')"
                    ev_html+="\nev_allday.push('0')"
                ev_html+="\nev_name.push(\""+event['summary']+"\")"
                ev_ctr+=1
            ev_html+="\nvar ev_ctr="+str(ev_ctr)+"\n"
            
            # generate html string of the web page
            html_str="""
<!doctype html>
<html>
    <head>
        <meta http-equiv="refresh" content="60"> 
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <script type="text/javascript" src="../lib/jquery.js"></script>
        <script type="text/javascript" src="../lib/moment.js"></script>
        <link rel="stylesheet" href="../fonts/OpenSansCondensed/stylesheet.css" type="text/css" charset="utf-8" />
        <script>
            var ev_start=new Array()
            var ev_end=new Array()
            var ev_name=new Array()
            var ev_allday=new Array()
            var ev_loc=new Array()
            var ev_dur=new Array()
            var i, len, progress

            // START: customisable variables

            var x_datetime_format="ddd DD MMM hh:mma"
            var x_datetime_format2="ddd DD MMM hh:mm:ssa"
            var x_allday_format="ddd DD MMM"
            
            // time format 12 hours am/pm
            var x_time_format="hh:mma"

            // progress
            var x_countdown_bar_duration=300 //seconds
            var x_countdown_bar_color="lightpink"
            var x_progress_bar_color="lightgreen"

            // END: customisable variables
            """
            html_str+=ev_html[1:]
            html_str+="""
            $(function(){
                for(i=0,len=ev_ctr;i<len;i++){
                    var start_date = new Date(ev_start[i]).getTime();
                    var end_date = new Date(ev_end[i]).getTime();
                    var dur=end_date-start_date
                    var dur_days = Math.floor(dur / (1000 * 60 * 60 * 24));
                    var dur_hours = Math.floor((dur % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                    var dur_minutes = Math.floor((dur % (1000 * 60 * 60)) / (1000 * 60));
                    var dur_seconds = Math.floor((dur % (1000 * 60)) / 1000);
                    var dur_str='_';
                    if(dur_days>0) dur_str+=dur_days+'<span class=small>d</span>';
                    if(dur_hours>0){
                        if(dur_str>'_') dur_str+=' ';
                        dur_str+=dur_hours+'<span class=small>h</span>';
                    }
                    if(dur_minutes>0){
                        if(dur_str>'_') dur_str+=' ';
                        dur_str+=dur_minutes+'<span class=small>m</span>';
                    }
                    dur_str=dur_str.substring(1);
                    ev_dur[i]=dur_str;
                    tr="<tr valign=top id=ev_"+i+" bgcolor=whitesmoke>";
                    tr+="<td id=progress_"+i+"><b>"+ev_name[i]+"</b><div class=small><b>";
                    if(ev_allday[i]==1){
                        tr+=moment(start_date).format(x_allday_format)+" - All Day<br>";
                    } else {
                        tr+=moment(start_date).format(x_datetime_format)+" - "
                        if(moment(start_date).format(x_allday_format)==moment(end_date).format(x_allday_format)) {
                        //if(dur<=(24 * 60 * 60 * 1000)){
                            tr+=moment(end_date).format(x_time_format);
                        } else {
                            tr+=moment(end_date).format(x_datetime_format);
                        }
                        tr+=' ('+dur_str+')';
                    }
                    tr+="</b></div>";
                    if(ev_loc[i]!="_NO_LOC_"){
                        if(ev_loc[i].length>40){
                            tr+="<div>"+ev_loc[i].substring(0,40)+"</div>";
                        } else {
                            tr+="<div>"+ev_loc[i]+"</div>";
                        }
                    }
                    tr+='</td>';
                    tr+="<td id=tminusplus_"+i+" nowrap></td>";
                    tr+="<td id=tdur_"+i+"  nowrap></td>";
                    tr+="<td id=val_"+i+" style='display:none'></td>";
                    tr+="</tr>"
                    $("#ev_tab tr:last").after(tr);
                }
                var x=setInterval(function(){
                    var now=new Date().getTime()
                    for(i=0,i<ev_ctr;i<len;i++){
                        var start_date = new Date(ev_start[i]).getTime();
                        var end_date = new Date(ev_end[i]).getTime();
                        var dur=end_date-start_date
                        if(start_date>now){
                            when=start_date
                            diff=start_date-now
                            elapsed=0
                        } else if(end_date>now) {
                            when=end_date
                            diff=end_date-now
                            elapsed=now-start_date
                        } else {
                            $("#tminusplus_"+i).html("Done");
                            $("#tminusplus_"+i).removeClass().addClass("tdone").css('textAlign','center');
                            $("#tdur_"+i).html(" ");
                            $("#tdur_"+i).removeClass().addClass("tdone");
                            $("#progress_"+i).removeClass().addClass('tdone');
                            diff=0
                            elapsed=0
                        }
                        $("#val_"+i).text(diff);
                        if(now<end_date){
                            var diff_days = Math.floor(diff / (1000 * 60 * 60 * 24));
                            var diff_hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                            var diff_minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                            var diff_seconds = Math.floor((diff % (1000 * 60)) / 1000);
                            timer_str="_"
                            if(diff_days>0){
                                timer_str+=diff_days+"<span class=small>d </span>"
                                if(diff_hours>0){
                                    timer_str+=diff_hours+"<span class=small>h </span>"
                                } else if(diff_minutes>0) {
                                    timer_str+=diff_minutes+"<span class=small>m </span>"
                                } else if(diff_seconds>0) {
                                    timer_str+=diff_seconds+"<span class=small>s </span>"
                                }
                            } else if(diff_hours>0){
                                timer_str+= diff_hours+"<span class=small>h </span>"
                                if(diff_minutes>0){
                                    timer_str+=diff_minutes+"<span class=small>m </span>"
                                } else if(diff_seconds>0){
                                    timer_str+=diff_seconds+"<span class=small>s </span>"
                                }
                            } else if(diff_minutes>0){
                                timer_str+= diff_minutes+"<span class=small>m </span>"
                                if(diff_seconds>0){
                                    timer_str+=diff_seconds+"<span class=small>s </span>"
                                }
                            } else {
                                timer_str+= diff_seconds+"<span class=small>s </span>"
                            }
                            var elap_days = Math.floor(elapsed / (1000 * 60 * 60 * 24));
                            var elap_hours = Math.floor((elapsed % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                            var elap_minutes = Math.floor((elapsed % (1000 * 60 * 60)) / (1000 * 60));
                            var elap_seconds = Math.floor((elapsed % (1000 * 60)) / 1000);
                            elap_str="_"
                            if(elap_days>0){
                                elap_str+=elap_days+"<span class=small>d </span>"
                                if(elap_hours>0){
                                    elap_str+=elap_hours+"<span class=small>h </span>"
                                } else if(elap_minutes>0) {
                                    elap_str+=elap_minutes+"<span class=small>m </span>"
                                } else if(elap_seconds>0) {
                                    elap_str+=elap_seconds+"<span class=small>s </span>"
                                }
                            } else if(elap_hours>0){
                                elap_str+= elap_hours+"<span class=small>h </span>"
                                if(elap_minutes>0){
                                    elap_str+=elap_minutes+"<span class=small>m </span>"
                                } else if(elap_seconds>0){
                                    elap_str+=elap_seconds+"<span class=small>s </span>"
                                }
                            } else if(elap_minutes>0){
                                elap_str+= elap_minutes+"<span class=small>m </span>"
                                if(elap_seconds>0){
                                    elap_str+=elap_seconds+"<span class=small>s </span>"
                                }
                            } else {
                                elap_str+= elap_seconds+"<span class=small>s </span>"
                            }
                            if(start_date>now){
                                $("#tminusplus_"+i).html(timer_str.substring(1));
                                $("#tdur_"+i).html(ev_dur[i]);
                                $("#tminusplus_"+i).removeClass().addClass("tminus");
                                $("#tdur_"+i).removeClass().addClass("tminus");
                                if(diff<=x_countdown_bar_duration*1000){
	                                progress=Math.floor((diff/1000)/x_countdown_bar_duration*100);
                                    $("#progress_"+i).css("background-image", "linear-gradient(to right, "+x_countdown_bar_color+" "+progress+"%, whitesmoke "+progress+"%");
                                }
                            } else if(end_date>now){
                                $("#tminusplus_"+i).html(elap_str.substring(1));
                                $("#tdur_"+i).html(timer_str.substring(1));
                                $("#tminusplus_"+i).removeClass().addClass("tplus");
                                $("#tdur_"+i).removeClass().addClass("tplus");
                                progress=Math.floor(elapsed/dur*100)+1
                                $("#progress_"+i).css("background-image", "linear-gradient(to right, "+x_progress_bar_color+" "+progress+"%, whitesmoke "+progress+"%");
                                //$("#tminusplus_"+i).html(progress+'<span class=small>%</span>');
                            }
                        }
                    }
                    tab_sort();
                    $("#clock").text(moment(now).format(x_datetime_format2))                   
                },1000)
            });
            function tab_sort(){
                var table = $("#ev_tab")
                var rows = table.find('tr:gt(0)').toArray().sort(comparer(3))
                for (var i = 0; i < rows.length; i++){table.append(rows[i])}
            }
            function comparer(index) {
                return function(a, b) {
                    var valA = getCellValue(a, index), valB = getCellValue(b, index)
                    return $.isNumeric(valA) && $.isNumeric(valB) ? valA - valB : valA.toString().localeCompare(valB)
                }
            }
            function getCellValue(row, index){ return $(row).children('td').eq(index).text() }
        </script>
        """
            style_big_font="""
            body,td {
                font-family: 'open_sans_condensedlight', Arial, sans-serif;
                font-size: 30px;
            }
            .small {font-size: 20px;}
            """
            style_small_font="""
            body,td {
                font-family: 'open_sans_condensedlight', Arial, sans-serif;
                font-size: 20px;
            }
            .small {font-size: 14px;}
            """
            style_both="""
            .tminus {
                border-radius: 5px 0px;
                background-color: black;
                color: white;
                text-align: center;
                vertical-align: middle;
                width: 12%;
            }
            .tplus {
                border-radius: 5px 0px;
                background-color: lightgreen;
                color: black;
                text-align: center;
                vertical-align: middle;
                width: 12%;
            }
            .tdone {
                border-radius: 5px 0px;
                background-color: lightslategray;
                color: white;
                vertical-align: middle;
            }
            .cols {
                font-size: 15px;
                background-color: black;
                color: white;
            }
            """
            style_big_str="<style>"+style_big_font+style_both+"</style></head>"
            style_small_str="<style>"+style_small_font+style_both+"</style></head>"
            body_str="""
    <body>
        <table id="ev_tab" width=100%>
            <tr align=center valign=top class=cols><td id=clock align=left></td><td nowrap>T-/+</td><td nowrap>DUR</td></tr>
        </table>
    </body>
</html>
        """
            f=open(self.html_big_file,'w')
            f.write(html_str + style_big_str + body_str)
            f.close()
            f=open(self.html_small_file,'w')
            f.write(html_str + style_small_str + body_str)
            f.close()