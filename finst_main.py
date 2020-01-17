import json
import time

from qpylib import logging
from qpylib.t import *
from qpylib.uidriver import chrome_driver
from qpylib.uidriver import chrome_ui_action

URL_PREFIX = 'https://www.instagram.com/'

# Number of scrolls on the tag page (to get more images).
NUM_OF_SCROLL_ON_TAG_PAGE = 20
# Control what images to like based on existing number of likes.
NUM_OF_MIN_LIKE = 3
NUM_OF_MAX_LIKE = 50

# If keyword repeats is greater than this value, it's very likely to be an Ad.
AD_KEYWORDS_REPEATS_THRESHOLD = 10


def FetchImageIdsFromTagPage(
    tag: Text,
    num_of_scrolls: int,
) -> Callable[[chrome_driver.ChromeDriver], List[Text]]:
  def Action(driver: chrome_driver.ChromeDriver):
    comm = driver.GetCommunicator()
    chrome_ui_action.GoToUrl(comm, URL_PREFIX + 'explore/tags/%s/' % tag)

    image_ids = set()
    image_ids = image_ids.union(_GetImageIdsAction(comm))
    for _ in range(num_of_scrolls):
      chrome_ui_action.ScrollToBottom(comm)
      time.sleep(1.5)
      image_ids = image_ids.union(_GetImageIdsAction(comm))
    return list(image_ids)

  return Action


def _GetImageIdsAction(comm: chrome_driver.ChromeCommunicator) -> List[Text]:
  return json.loads(comm.RunJs_GetValue("""
    ids = [];
    for (let aElem of document.querySelectorAll('a[href*="/p/"]')) { 
      ids.push(aElem.href.split('/')[4]);
    }
    JSON.stringify(ids);
    """))


def _PerformLikeAction_OLD_20200105(
    image_id: Text,
    num_of_maximum_like: int,
) -> Callable[[chrome_driver.ChromeDriver], bool]:
  get_like_button_command = (
    'likeButton = document.querySelector('
    '"span[class*=glyphsSpriteHeart]:not([class*=white])");')

  def Action(driver: chrome_driver.ChromeDriver) -> bool:
    comm = driver.GetCommunicator()
    chrome_ui_action.GoToUrl(comm, URL_PREFIX + 'p/%s/' % image_id)

    number_of_likes = int(comm.RunJs_GetValue(get_like_button_command + """
    likeText = likeButton.parentElement.parentElement.parentElement.parentElement.children[1].innerText;
    likeText.split(" ")[0].replace(",", "");
    """))
    if number_of_likes >= num_of_maximum_like:
      logging.vlog(3, 'image %s has %d likes; ignore', image_id,
                   number_of_likes)
      return False

    is_liked = comm.RunJs_GetValue(get_like_button_command + """
    likeButton.className.indexOf('filled') != -1;
    """)
    if not is_liked:
      comm.RunJs(get_like_button_command + 'likeButton.click();')
      logging.vlog(10, 'liked image %s', image_id)
      return True
    else:
      logging.vlog(5, 'image %s is already liked; ignore', image_id)

  return Action


def PerformLikeAction(
    image_id: Text,
    num_of_minimum_likes: int,
    num_of_maximum_likes: int,
    ad_keyword_repeats_threshold: int,
) -> Callable[[chrome_driver.ChromeDriver], bool]:
  get_like_button_command = ("""
    likeButton = (function() {
      var buttons = document.querySelectorAll("svg[aria-label=Like]");
      for (var button of buttons) {
        if (button.getAttribute("fill") == "#262626") {
          return button.parentElement;
        }
      }
      return null;
    })();
    """)

  def Action(driver: chrome_driver.ChromeDriver) -> bool:
    comm = driver.GetCommunicator()
    chrome_ui_action.GoToUrl(comm, URL_PREFIX + 'p/%s/' % image_id)

    number_of_likes = int(comm.RunJs_GetValue(get_like_button_command + """
    num_of_likes = 0;
    if (likeButton != null) {
      likeText = likeButton.parentElement.parentElement.parentElement.children[1].innerText;
      if (likeText.indexOf("Be the first") != -1) {
        num_of_likes = 0;
      } else {
        num_of_likes = likeText.split(" ")[0].replace(",", "");
      }
    } else {
      num_of_likes = -1;
    }
    num_of_likes;
    """))
    if (number_of_likes >= num_of_maximum_likes or
        number_of_likes <= num_of_minimum_likes):
      logging.vlog(3, 'image %s has %d likes; ignore', image_id,
                   number_of_likes)
      return False
    elif number_of_likes == -1:
      logging.vlog(5, 'image %s is already liked; ignore', image_id)
      return False

    keywordsRepeats = int(comm.RunJs_GetValue(get_like_button_command + """
    comments = likeButton.parentElement.parentElement.parentElement.children[2].innerText;
    var segments = comments.split(/[ ,-_#\\n]/);
    var sanitizedSegments = [];
    for (var seg of segments) {
      if (seg.length > 3) {
        sanitizedSegments.push(seg);
      }
    }
    var repeats = 0;
    for (var i = 0; i < sanitizedSegments.length; i++) {
      for (var j = i+1; j < sanitizedSegments.length; j++) {
        let seg1 = sanitizedSegments[i];
        let seg2 = sanitizedSegments[j];
        if (seg1.indexOf(seg2) > -1 || seg2.indexOf(seg1) > -1) {
          repeats += 1;
        }
      }
    }
    repeats;
    """))
    logging.vlog(
      5, 'image %s has %d keyword repeats', image_id, keywordsRepeats)
    if keywordsRepeats > ad_keyword_repeats_threshold:
      logging.vlog(5, 'image %s is likely an Ad; ignore', image_id)
      return False

    comm.RunJs(get_like_button_command + 'likeButton.click();')
    logging.vlog(10, 'liked image %s', image_id)
    return True

  return Action


def LikeImagesWithTag(
    manager: chrome_driver.ChromeDriverManager,
    tag: Text,
    num_of_scrolls: int = NUM_OF_SCROLL_ON_TAG_PAGE,
    num_of_minimum_likes: int = NUM_OF_MIN_LIKE,
    num_of_maximum_likes: int = NUM_OF_MAX_LIKE,
    ad_keyword_repeats_threshold: int = AD_KEYWORDS_REPEATS_THRESHOLD,
) -> None:
  image_ids = manager.Do(
    FetchImageIdsFromTagPage(tag=tag, num_of_scrolls=num_of_scrolls))
  logging.vlog(
    2, "Number of images fetched: %d: IDs: %s", len(image_ids), image_ids)
  for image_id in image_ids:
    manager.Do(
      PerformLikeAction(
        image_id,
        num_of_minimum_likes=num_of_minimum_likes,
        num_of_maximum_likes=num_of_maximum_likes,
        ad_keyword_repeats_threshold=ad_keyword_repeats_threshold,
      ))


def LikeImagesWithTags(
    manager: chrome_driver.ChromeDriverManager,
    tags: List[Text],
) -> None:
  for tag in tags:
    LikeImagesWithTag(
      manager,
      tag)


def Main():
  logging.ENV.debug_verbosity = 20
  manager = chrome_driver.ChromeDriverManager()
  LikeImagesWithTags(
    manager,
    [
      # 'foodie',
      'tourism',
      'everydaylife',
    ])


if __name__ == '__main__':
  Main()
