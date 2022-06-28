import concurrent.futures
import json
import os
from urllib.parse import urlparse

import html2text
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil.parser import parse as date_parse
from jinja2 import Template

DATA_ROOT_DIR = "/data"

# from the example.com/guests page by show web hostname and then by username
SHOW_GUESTS = {}

# Missing data found in a show. Used to scrape and/or create these files after the
# episode files been created.
MISSING_SPONSORS = {}
MISSING_HOSTS = set()
MISSING_GUESTS = set()


"""
Global to hold scraped data about episodes from jupiterbroadcasting.com.

The structure of this is:

{
    "show_slug": {   # <-- as defined in config.yml
        123: {   # <-- ep number
            "youtube_link": "...",
            "video_link": "...",
            ...
            ...
            "key_1": "value"
        }
    },
    "show_slug_2": { 
        ...
    }
}
"""
JB_DATA = {}


with open("templates/episode.md.j2") as f:
    TEMPLATE = Template(f.read())


def mkdir_safe(directory):
    try:
        os.makedirs(directory)
    except FileExistsError:
        pass


def get_list(soup, pre_title, find_tag="p", sibling_tag="ul"):
    """
    Blocks of links are preceded by a find_tag (`p` default) saying what it is.
    """
    pre_element = soup.find(find_tag, string=pre_title)
    if pre_element is None:
        return None
    return pre_element.find_next_sibling(sibling_tag)


def seconds_2_hhmmss_str(seconds):
    if type(seconds) == str:
        seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def get_plain_title(title: str):
    """
    Get just the show title, without any numbering etc
    """
    # Remove number before colon
    title = title.split(":", 1)[-1]

    # Remove data after the pipe
    title = title.rsplit("|", 1)[0]

    # Strip any stray spaces
    return title.strip()


def create_episode(api_episode, show_config, show_slug, hugo_data, output_dir):
    try:
        mkdir_safe(output_dir)

        # RANT: What kind of API doesn't give the episode number?!
        episode_number = int(api_episode["url"].split("/")[-1])
        episode_number_padded = f"{episode_number:03}"

        output_file = f"{output_dir}/{episode_number}.md"

        if os.path.isfile(output_file):
            Log.info(f"Skipping saving `{output_file}` as it already exists")
            return

        publish_date = date_parse(api_episode['date_published'])

        api_soup = BeautifulSoup(api_episode["content_html"], "html.parser")
        page_soup = BeautifulSoup(requests.get(
            api_episode["url"]).content, "html.parser")

        blurb = api_episode["summary"]

        sponsors = parse_sponsors(
            hugo_data, api_soup, page_soup, show_config["acronym"], episode_number)

        links = html2text.html2text(
            str(get_list(api_soup, "Links:") or get_list(api_soup, "Episode Links:")))

        tags = []
        for link in page_soup.find_all("a", class_="tag"):
            tags.append(link.get_text().strip())

        tags = sorted(tags)

        hosts = parse_hosts(hugo_data, page_soup,
                            show_config, episode_number)

        guests = parse_guests(hugo_data, page_soup,
                              show_config, episode_number)

        show_attachment = api_episode["attachments"][0]

        jb_ep_data = JB_DATA.get(show_slug, {}).get(episode_number, {})

        output = TEMPLATE.render(
            {
                # "title": api_episode["title"],
                "title_plain": get_plain_title(api_episode["title"]),
                "blurb": blurb,
                "date_published": publish_date.date().isoformat(),
                "is_draft": "false",
                # TODO: In what case should the "Featured" category be added?
                "categories": [show_config["name"]],
                "tags": tags,
                "hosts": hosts,
                "guests": guests,
                "sponsors": sponsors,
                "header_image": show_config["header_image"],

                "episode_number": episode_number,
                "episode_number_padded": episode_number_padded,
                "podcast_duration": seconds_2_hhmmss_str(show_attachment['duration_in_seconds']),
                # TODO: the url in fireside is prefixed using https://chtbl.com not http://www.podtrac.com. Should this be left as is or changed to use podtrac?
                "podcast_file": show_attachment["url"],
                "podcast_file_podtrack": jb_ep_data.get("mp3_audio", ""),
                "podcast_file_ogg": jb_ep_data.get("ogg_audio", ""),
                "podcast_bytes": show_attachment.get("size_in_bytes", ""),
                # "url": api_episode.get("url", ""),

                # TODO: leave empty or use None?
                "youtube_link": jb_ep_data.get("youtube", ""),
                # TODO: leave empty or use None?
                "video_file": jb_ep_data.get("video", ""),
                "video_file_hd": jb_ep_data.get("hd_video", ""),
                "video_file_mobile": jb_ep_data.get("mobile_video", ""),
                "jb_legacy_url": jb_ep_data.get("jb_url", ""),

                "links": links
            }
        )

        with open(output_file, "w") as f:
            Log.info(f"Saving episode from {api_episode['url']}")
            f.write(output)

    except Exception as e:
        Log.err(f"Failed to create an episode from url!",
                episode_url=api_episode.get('url'),
                exception=e)


def parse_hosts(hugo_data, page_soup: BeautifulSoup, show_config, ep):
    show = show_config["acronym"]
    base_url = show_config["fireside_url"]

    hosts = []

    # assumes the hosts are ALWAYS the first <ul> and guests are in the second one
    hosts_links = page_soup.find("ul", class_="episode-hosts").find_all("a")

    # hosts_links = page_soup.select(".episode-hosts ul:first-child a")
    for link in hosts_links:
        try:
            host_name = link.get("title").strip()

            host = hugo_data["hosts"]["_data"].get(host_name)
            if host:
                hosts.append(host["username"])
            else:
                # Log.warn("Missing HOST definition",
                #          show=show, ep=ep, host_name=host_name)
                host_page_url = base_url + link.get("href")
                MISSING_HOSTS.add(host_page_url)
                hosts.append(get_username_from_url(host_page_url))
        except Exception as e:
            Log.error(f"Failed to parse HOST for link href!",
                    href=link.get('href'),
                    exception=e)
    return hosts


def parse_guests(hugo_data, page_soup, show_config, ep):
    show = show_config["acronym"]
    base_url = show_config["fireside_url"]

    guests = []

    # assumes the hosts are ALWAYS the first <ul> and guests are in the second one
    # <- this would always be the hosts list
    hosts_list = page_soup.find("ul", class_="episode-hosts")
    # look for the NEXT `ul.episode-hosts`, that should be the guests list (might not exist)
    guests_list = hosts_list.find_next("ul", class_="episode-hosts")
    if not guests_list:
        return guests

    guests_links = guests_list.find_all("a")
    for link in guests_links:
        try:
            guest_name = link.get("title").strip()

            guest = hugo_data["guests"]["_data"].get(guest_name)
            # Sometimes the guests are already defined in the hosts, for example if they
            # are hosts in a different show. So try to find the within hosts.
            host_guest = hugo_data["hosts"]["_data"].get(guest_name)

            if guest:
                guests.append(guest["username"])
            elif host_guest:
                guests.append(host_guest["username"])
            else:
                # Log.warn("Missing GUEST definition",
                #          show=show, ep=ep, host_name=guest_name)
                guest_page_url = base_url + link.get("href")
                MISSING_GUESTS.add(guest_page_url)
                guests.append(get_username_from_url(guest_page_url))

        except Exception as e:
            Log.error(f"Failed to parse GUEST for link href!",
                    href=link.get('href'),
                    exception=e)

    return guests


def parse_sponsors(hugo_data, api_soup, page_soup, show, ep):
    # Get only the links of all the sponsors
    sponsors_ul = get_list(api_soup, "Sponsored By:")
    if not sponsors_ul:
        Log.warn("No sponsors found for this episode.", show=show, ep=ep)
        return []

    sponsors_links = [a["href"]
                      for a in sponsors_ul.select('li > a:first-child')]

    sponsors = []
    for sl in sponsors_links:
        try:
            s = hugo_data["sponsors"]["_data"].get(sl)
            if s:
                sponsors.append(s["shortname"])
            else:
                # Log.warn("Missing SPONSOR definition",
                #          show=show, ep=ep, sponsor_link=sl)

                # Very ugly but works. The goal is to get the hostname of the sponsor
                # link without the subdomain. It would fail on tlds like "co.uk". but I
                # don't think JB had any sponsors like that so it's fine.
                sponsor_slug = ".".join(urlparse(sl).hostname.split(".")[-2:])
                shortname = f"{sponsor_slug}-{show}".lower()
                sponsors.append(shortname)

                filename = f"{shortname}.json"

                # Find the <a> element on the page with the link
                sponsor_a = page_soup.find(
                    "div", class_="episode-sponsors").find("a", attrs={"href": sl})
                if sponsor_a:
                    MISSING_SPONSORS.update({
                        filename: {
                            "shortname": shortname,
                            "name": sponsor_a.find("header").text.strip(),
                            "description": sponsor_a.find("p").text.strip(),
                            "link": sl
                        }
                    })
        except Exception as e:
            Log.error("Failed to collect/parse sponsor data!",
                      show=show, ep=ep, exception=e)

    return sponsors


def save_json_file(filename, json_obj, dest_dir):
    mkdir_safe(dest_dir)

    file_path = os.path.join(dest_dir, filename)

    with open(file_path, "w") as f:
        f.write(json.dumps(json_obj, indent=4))

    Log.debug("Saved new json file", file=file_path)


def read_hugo_data():
    hugo_data = {
        "guests": {
            "_key": "name",
            "_data": {}
        },
        "hosts": {
            "_key": "name",
            "_data": {}
        },
        "sponsors": {
            "_key": "link",
            "_data": {}
        }
    }

    for key, item in hugo_data.items():
        files_dir = f"/hugo-data/{key}"
        json_files = os.listdir(files_dir)

        for file in json_files:
            file_path = f"{files_dir}/{file}"
            with open(file_path, "r") as f:
                json_data = json.loads(f.read())
                data_key = json_data.get(item["_key"])

                if not data_key:
                    Log.error(f"read_hugo_data: Skipping file `{file_path}` since it "
                              f"doesn't have the expected key `{item._key}`")
                    continue

                item["_data"].update({data_key: json_data})

    # hugo_data_debug = json.dumps(hugo_data, indent=2)
    # print(f"read_hugo_data: {hugo_data_debug}")

    return hugo_data


def get_username_from_url(url):
    """
    Get the last path part of the url which is the username for the hosts and guests
    """
    return urlparse(url).path.split("/")[-1]


def create_host_or_guest(url, dirname):
    try:
        valid_dirnames = {"hosts", "guests"}
        assert dirname in valid_dirnames, "dirname arg must be one of `hosts`, `guests`"

        page_soup = BeautifulSoup(requests.get(url).content, "html.parser")
        
        username = get_username_from_url(url)  

        show_url = url.split("/guests")[0]

        # From guests list page. Need this because sometimes the single guest page
        # is missing info (e.g. all self-hosted guests)
        guest_data = SHOW_GUESTS.get(show_url, {}).get(username, {})  

        # Fallback name to be to username
        name = username

        name_h1 = page_soup.find("h1")
        if name_h1:
            name = name_h1.text.strip()
        elif guest_data: 
            name = guest_data.get("name", username)
        

        if guest_data:
            avatar_url = guest_data.get("avatar")
        else:
            avatar_div = page_soup.find("div", class_="hero-avatar")
            avatar_url = avatar_div.find("img").get("src")
        
        avatars_dir = os.path.join(DATA_ROOT_DIR, "static", "images", dirname)
        mkdir_safe(avatars_dir)

        filename = f"{username}.jpg"
        avatar_file = os.path.join(avatars_dir, filename)

        with open(avatar_file, "wb") as f:
            f.write(requests.get(avatar_url).content)

        # Get social links

        homepage = None
        twitter = None
        linkedin = None
        instagram = None
        gplus = None
        youtube = None
        links = page_soup.find("nav", class_="links").find_all("a")

        # NOTE: This will work only if none of the links are shortened urls
        for link in links:
            href = link.get("href").lower()
            if "Website" in link.text:
                homepage = href
            elif "twitter" in href:
                twitter = href
            elif "linkedin" in href:
                linkedin = href
            elif "instagram" in href:
                instagram = href
            elif "google" in href:
                gplus = href
            elif "youtube" in href:
                youtube = href
        
        bio = ""
        _bio = page_soup.find("section")
        if _bio:
            bio = _bio.text.strip()

        host_json = {
            "username": username,  # e.g. "alexktz"
            "name": name,  # e.g. "Alex Kretzschmar"
            # e.g. "Red Hatter. Drone Racer. Photographer. Dog lover."
            "bio":  bio,
            # e.g. "/images/guests/alex_kretzschmar.jpeg"
            "avatar":  f"/images/{dirname}/{filename}",
            "homepage": homepage,  # e.g. "https://www.linuxserver.io/"
            "twitter": twitter,  # e.g. "https://twitter.com/ironicbadger"
            # e.g. "https://www.linkedin.com/in/alex-kretzschmar/""
            "linkedin": linkedin,
            "instagram": instagram,
            "gplus": gplus,
            "youtube": youtube,
        }

        hosts_dir = os.path.join(DATA_ROOT_DIR, "data", dirname)
        save_json_file(f"{username}.json", host_json, hosts_dir)
    except Exception as e:
        Log.error("Failed to create/save a new host/guest file!",
                  url=url, exception=e)


def main():
    with open("config.yml") as f:
        shows = yaml.load(f, Loader=yaml.SafeLoader)['shows']

    hugo_data = read_hugo_data()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Must be first. Here the JB_DATA global is populated
        scrape_data_from_jb(shows, executor)

        # save to a json file - this might be useful for files migrations
        jb_file = os.path.join(DATA_ROOT_DIR, "jb_all_shows_links.json")
        with open(jb_file, "w") as f:
            f.write(json.dumps(JB_DATA, indent=2))

        scrape_episodes_from_fireside(shows, hugo_data, executor)

        # Must come after scrape_episodes_from_fireside where the MISSING_* globals
        # are set
        scrape_hosts_guests_and_sponsors(shows, executor)

    Log.info(">>> 🔥🔥🔥 ALL DONE :) 🔥🔥🔥\n\n")

def scrape_data_from_jb(shows, executor):
    Log.info(">>> Scraping data from jupiterbroadcasting.com...")

    # Collect all links for epsidoe page of each show into JB_DATA
    futures = []
    for show_slug, show_config in shows.items():
        show_base_url = show_config["jb_url"]
        futures.append(executor.submit(
            jb_populate_episodes_urls, show_slug, show_base_url))
    for future in concurrent.futures.as_completed(futures):
        future.result()

    Log.info(">>> Finished collecting all episode page urls") 

    # Scrape each page for data
    futures = []
    for show, show_episodes in JB_DATA.items():
        for ep, ep_data in show_episodes.items():
            futures.append(executor.submit(
                jb_populate_direct_links_for_episode, ep_data, show, ep))
    for future in concurrent.futures.as_completed(futures):
        future.result()

    Log.info(">>> Finished scraping data from jupiterbroadcasting.com ✓")

def jb_populate_direct_links_for_episode(ep_data, show, ep):
    try:
        ep_soup = BeautifulSoup(requests.get(
            ep_data["jb_url"]).content, "html.parser")
        dd_div = ep_soup.find("div", attrs={"id": "direct-downloads"})
        if dd_div:
            dl_links = dd_div.find_all("a")
        else:
            # older episodes have different structure.
            p_links = get_list(ep_soup, "Direct Download:", "h3", "p")
            if p_links:
                dl_links = p_links.find_all("a")
            else:
                Log.warn("Failed to find Direct Download links for the episode.",
                         show=show, ep=ep)
                return

        for dl_link in dl_links:
            url = dl_link.get("href").strip("\\\"")
            slug = dl_link.text.lower().replace(" ", "_")
            ep_data.update({
                slug: url
            })
    except Exception as e:
        Log.error("Failed to parse direct links for episode.",
                  show=show, ep=ep, exception=e)


def jb_populate_episodes_urls(show_slug, show_base_url):
    show_data = {}
    JB_DATA.update({show_slug: show_data})

    page_soup = BeautifulSoup(requests.get(
        show_base_url).content, "html.parser")
    pages_span = page_soup.find("span", class_="pages")
    if pages_span:
        last_page = pages_span.text.split(" ")[-1]
        last_page = int(last_page)
    else:
        last_page = 1  # Just one page

    for page in range(1, last_page+1):
        if page > 1:
            page_url = f"{show_base_url}/page/{page}/"
            page_soup = BeautifulSoup(requests.get(
                page_url).content, "html.parser")

        videoitems = page_soup.find_all("div", class_="videoitem")
        for idx, item in enumerate(videoitems):
            try:
                link = item.find("a")
                link_href = link.get("href")
                ep_num = link.get("title").split(" ")[-1]

                if ep_num == "LU1":
                    # LUP edge case for ep 1
                    ep_num = 1
                if link.get("title") == "Goodbye from Linux Action News":
                    # LAN edge case. This ~2 message is between ep152 and 153, hence it
                    # shall be offically titled as episode 152.5 for now forth
                    # (hopefully having floaty number won't brake things 😛)
                    ep_num = 152.5
                # Some coder exceptins
                if link.get("title") == "Say My Functional Name | Coder Radio":
                    ep_num = 343
                if link.get("title") == "New Show! | Coder Radio":
                    ep_num = 0
                else:
                    ep_num = int(ep_num)

                show_data.update({ep_num: {
                    "jb_url": link_href
                }})
            except Exception as e:
                Log.error("Failed to get episode page link and number from JB site.",
                      show=show_slug, exception=e, page=page, ep_idx=idx, html=item.string)


def scrape_hosts_guests_and_sponsors(shows, executor):
    output_dir = os.path.join(DATA_ROOT_DIR, "data", "sponsors")
    mkdir_safe(output_dir)
    # no need to do thread since there's only a handful number of shows
    for show_slug, show_data in shows.items():
        allg_url = f"{show_data['fireside_url']}/guests"
        guests_soup = BeautifulSoup(requests.get(allg_url).content, "html.parser")
        links = guests_soup.find("ul", class_="show-guests").find_all("a")
        for l in links:
            
            username = l.get("href").rstrip("/").split("/")[-1]
            name = l.find("h5").text.strip()
            avatar_sm = l.find("img").get("src").split("?")[0]
            avatar = avatar_sm.replace("_small.jpg", ".jpg")

            SHOW_GUESTS.update({
                show_data['fireside_url']: {
                    username: {
                        "username": username,
                        "name": name,
                        "avatar_sm": avatar_sm,
                        "avatar": avatar
                    }
                }
            })


    # ****

    futures = []
    
    # MISSING_SPONSORS:
    for filename, sponsor in MISSING_SPONSORS.items():
        futures.append(executor.submit(
            save_json_file, filename, sponsor, output_dir))

    # MISSING_HOSTS:
    for url in MISSING_HOSTS:
        futures.append(executor.submit(create_host_or_guest, url, "hosts"))

    # MISSING_GUESTS:
    for url in MISSING_GUESTS:
        futures.append(executor.submit(create_host_or_guest, url, "guests"))

    # Drain to get exceptions. Still have to mash CTRL-C, though.
    for future in concurrent.futures.as_completed(futures):
        future.result()


def scrape_episodes_from_fireside(shows, hugo_data, executor):
    Log.info(">>> Scraping data from fireside...")

    futures = []
    for show_slug, show_config in shows.items():
        # Use same structure as in the root project for easy copy over
        output_dir = os.path.join(
            DATA_ROOT_DIR, "content", "show", show_slug)
        mkdir_safe(output_dir)

        api_data = requests.get(
            show_config['fireside_url'] + "/json").json()

        for idx, api_episode in enumerate(api_data["items"]):
            futures.append(executor.submit(
                create_episode, api_episode, show_config,
                show_slug, hugo_data, output_dir
            ))

        # Drain to get exceptions. This is important in order to collect all the
        # MISSING_* globals first before proceeding
    for future in concurrent.futures.as_completed(futures):
        future.result()
    Log.info(">>> Finished scraping from fireside ✓")

class Log:

    @staticmethod
    def log(lvl, msg, show=None, ep=None, **kwargs):
        out = f"{lvl} | "
        if show:
            out += f"{show} "
            if ep:
                out += f"{ep} "
            out += "| "
        out += f"{msg} "
        for k, v in kwargs.items():
            out += f"\n  {k}: `{v}`"
        print(out)

    @staticmethod
    def error(msg, show=None, ep=None, **kwargs):
        Log.log("ERROR", msg, show=show, ep=ep, **kwargs)

    @staticmethod
    def warn(msg, show=None, ep=None, **kwargs):
        Log.log("WARN", msg, show=show, ep=ep, **kwargs)

    @staticmethod
    def debug(msg, show=None, ep=None, **kwargs):
        Log.log("DEBUG", msg, show=show, ep=ep, **kwargs)

    @staticmethod
    def info(msg, show=None, ep=None, **kwargs):
        Log.log("INFO", msg, show=show, ep=ep, **kwargs)


if __name__ == "__main__":
    Log.info("🚀🚀🚀 SCRAPER STARTED! 🚀🚀🚀")
    main()
