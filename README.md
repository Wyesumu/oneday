This project is web realization of the art challenge called "1day1page". The idea is some artists register on the platform and they have to upload art every day if they didn't access is blocked and now they are watch-only.

=About web-site=

== Index page contains:
- Gallery of last 60 uploaded arts
- Clicking on nickname will open gallery with artist's works only
- Timer to block access

== User list contains:
- List of all users with stats: amout of uploaded arts and date of last art
- Near every user admin have button to block or give access to uploading

== Upload page:
- You can upload several files at the same time but this files will be inside one post (it was made to upload several images with progress of work if artist want to show it)
- If uploaded file is GIF thumbnail will have "Animated" tag on it
- If you check "NSFW" box thumbnail will be blurred
- Artist can specify date of art

== Calendar:
- Calendar is based on FullCalendar JS project
- Event is got from json /data page
- Every uploaded art will show here with username and post name in title. Clicking event will open page with this art


In work you can see it here: https://1day1page.tk

You can ask me any question. I will be glad to help you!

==about privileges:

privileges is coded in numbers:

1 is admin. Admin won't show in users list

2 is a curator of the project. Usually also upload works, can delete any work and ban/reset artists.

3 is general artist. All new users have this level. Can delete it's own arts

4 is banned. Can't upload, but can delete it's own arts.
