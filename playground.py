import json
import time

from qpylib import logging
from qpylib.t import *
from qpylib.uidriver import chrome_driver
from qpylib.uidriver import chrome_ui_action

URL_PREFIX = 'https://www.instagram.com/'

# Number of scrolls on the tag page (to get more images).
NUM_OF_SCROLL_ON_TAG_PAGE = 2
# Images with more than this number of likes are ignored.
NUM_OF_MAX_LIKE = 30


def FetchImageIdsFromTagPage(
    tag: Text,
    num_of_scrolls: int,
) -> Callable[[chrome_driver.ChromeDriver], List[Text]]:
  def Action(driver: chrome_driver.ChromeDriver):
    comm = driver.GetCommunicator()
    chrome_ui_action.GoToUrl(comm, URL_PREFIX + 'explore/tags/%s/' % tag)

    image_ids = set()
    for _ in range(num_of_scrolls):
      image_ids = image_ids.union(_GetImageIdsAction(comm))
      chrome_ui_action.ScrollToBottom(comm)
      time.sleep(1.5)
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


def PerformLikeAction(
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


def LikeImagesWithTag(
    manager: chrome_driver.ChromeDriverManager,
    tag: Text,
    num_of_scrolls: int = NUM_OF_SCROLL_ON_TAG_PAGE,
    num_of_maximum_like: int = NUM_OF_MAX_LIKE,
) -> None:
  image_ids = manager.Do(
    FetchImageIdsFromTagPage(tag=tag, num_of_scrolls=num_of_scrolls))
  logging.vlog(
    2, "Number of images fetched: %d: IDs: %s", len(image_ids), image_ids)
  for image_id in image_ids[:5]:
    manager.Do(
      PerformLikeAction(image_id, num_of_maximum_like=num_of_maximum_like))


def Main():
  logging.ENV.debug_verbosity = 20
  manager = chrome_driver.ChromeDriverManager()
  LikeImagesWithTag(manager, '吃吃吃', num_of_scrolls=2, num_of_maximum_like=50)


if __name__ == '__main__':
  Main()
