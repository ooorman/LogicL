import json
import math
import os
import sys
from collections import deque
import pygame

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # Для Windows 8.1+
except:
    pass

class ButtonStyle:
    def __init__(self, color, color_hover, font_size, outline=None):
        self.color = color
        self.color_hover = color_hover
        self.outline = outline
        self.font = pygame.font.SysFont('arial', font_size)

class Button(pygame.sprite.Sprite):
    def __init__(self, button_style, rect, callback, text):
        super().__init__()
        self.callback = callback
        self.text = text
        self.rect = rect
        self.change_button_style(button_style)

    def change_text(self, text):
        self.text = text
        self.change_button_style(self.button_style)

    def change_pos(self, new_pos):
        self.rect = pygame.Rect(*new_pos, *self.rect.size)

    def change_button_style(self, new_button_style):
        self.button_style = new_button_style
        temp_rect = pygame.Rect(0, 0, *self.rect.size)
        self.idle_image = self.create_image(new_button_style.color, temp_rect, self.text)
        self.hover_image = self.create_image(new_button_style.color_hover, temp_rect, self.text)
        self.image = self.idle_image
    def to_excited(self,new_buttonstyle=None, new_text=None):
        '''Когда при нажатии на кнопку происходит ввод информации постепенно.'''
        if not hasattr(self, 'idle_text'):
            self.idle_text = self.text
            self.idle_buttonstyle = self.button_style
            if new_text: self.change_text(new_text)
            if new_buttonstyle: self.change_button_style(new_buttonstyle)
    def to_unexcited(self):
        '''Когда информация введена и можно возвращать кнопку в исходное положение'''
        if hasattr(self, 'idle_text'):
            self.change_text(self.idle_text)
            self.change_button_style(self.idle_buttonstyle)
            del self.idle_text
            del self.idle_buttonstyle
    def create_image(self, color, rect, text):
        img = pygame.Surface(rect.size)
        if self.button_style.outline:
            img.fill(self.button_style.outline)
            img.fill(color, rect.inflate(-4, -4))
        else:
            img.fill(color)

        if text != '':
            text_surf = self.button_style.font.render(text, True, (0,0,0))
            text_rect = text_surf.get_rect(center=rect.center)
            img.blit(text_surf, text_rect)
        return img
    def update(self, events, offset=None):
        pos = list(pygame.mouse.get_pos())

        if offset:
            pos[0] -= offset[0]
            pos[1] -= offset[1]
        hit = self.rect.collidepoint(pos)
        self.image = self.hover_image if hit else self.idle_image
        for index, event in enumerate(events):
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and hit:
                self.callback()
                return True # в случае, если надо остановить перебор кнопок после нажатия одной

pygame.init()

CAMERA_SPEED = 5
MENU_CAMERA_SPEED = 5

MENU_WIDTH, MENU_HEIGHT = 1000, 1000 # должно делиться на 2

CIRCUIT_PANEL_WIDTH = 315 # должно делиться на 5
WHITE, BLACK, RED, GREEN, YELLOW = (255,255,255), (0,0,0), (255, 0, 0), (0,255,0), (255,255, 0)
CIRCUITS_PATH = 'saves/circuits/'
PLUGIN_CIRCUITS_PATH = 'saves/plugin_circuits/'
GRID_OUTLINE = 1
ALLOWED_IO_COUNT = 40
MAX_BLOCKSIZE = 50

CUSTOM_HEIGHT = 2
CUSTOM_COLOR = (136, 136, 136)

WHITE_BUTTONSTYLE = ButtonStyle(WHITE, (150,150,150), 20, BLACK)
SMALL_WHITE_BUTTONSTYLE = ButtonStyle(WHITE, (150,150,150), 15, BLACK)
RED_BUTTONSTYLE = ButtonStyle(RED, (150,0,0), 20, BLACK)
SMALL_RED_BUTTONSTYLE = ButtonStyle(RED, (150,0,0), 15, BLACK)
GREEN_BUTTONSTYLE = ButtonStyle(GREEN, (0, 150, 0), 20, BLACK)
SMALL_GREEN_BUTTONSTYLE = ButtonStyle(GREEN, (0, 150, 0), 15, BLACK)

MAX_IO_NAME_LEN = 7
FILE_ACCEPTS_CHARS_APPEND = ['_', ' ']
COMMENT_ACCEPTS_CHARS_APPEND = list(r'''-+/*=\/'"~?.,;(){}[]_ ''')
FPS = 60
CLOCK = pygame.time.Clock()
pygame.display.set_caption('LogicL')
def point_to_line_distance(px, py, x1, y1, x2, y2):
    """Возвращает расстояние от точки (px, py) до отрезка (x1, y1)-(x2, y2)."""
    # Векторы
    v = (x2 - x1, y2 - y1)
    w = (px - x1, py - y1)

    # Длина вектора
    len_squared = v[0] ** 2 + v[1] ** 2
    if len_squared == 0:  # Сегмент - это точка
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)

    # Проекция
    t = (w[0] * v[0] + w[1] * v[1]) / len_squared
    t = max(0, min(1, t))  # Ограничиваем от 0 до 1

    # Ближайшая точка на отрезке
    nearest_x = x1 + t * v[0]
    nearest_y = y1 + t * v[1]

    # Возвращаем расстояние до ближайшей точки
    return math.sqrt((px - nearest_x) ** 2 + (py - nearest_y) ** 2)
def nonrepeating_name(name, collection, suffix='', i=1):
    old_name = name
    while name + suffix in collection:
        name = f'{old_name}_{i}'
        i+=1

    return name
def at_least_1_lighting(el, input_key):
    return any(el_data[0].ios[1][el_data[1]][1] for el_data in el.ios[0][input_key])

class Element:

    rotate_state = 0
    size = [1,1]

    def __init__(self, *args, is_visible=True):
        # args - x, y, gw | x, y, gw, file_name | gw | gw, file_name
        if is_visible:
            self.x = args[0]
            self.y = args[1]
        self.gw = args[2] if is_visible else args[0]
        self.set_real_size()
    def set_pos(self, x, y):
        '''Устанавливает позицию для элемента относительно глобального нуля мира, записывает реальные координаты'''
        self.x = x
        self.y = y
        self.set_real_position()
    def get_real_pos(self):
        ''' Получение реальной позиции относительно левого верхнего угла камеры. '''
        return [self.__real_x - self.gw.camera_pos[0], self.__real_y - self.gw.camera_pos[1]]
    def set_real_position(self):
        ''' Запись реальной позиции относительно глобального нуля мира. '''
        self.__real_x = self.x * self.gw.blocksize + GRID_OUTLINE
        self.__real_y = self.y * self.gw.blocksize + GRID_OUTLINE
    def set_real_size(self):
        self.real_size = [-self.size[0] * self.gw.blocksize, -self.size[1] * self.gw.blocksize]
    def rotate(self, n=1):
        if n == 0: return

        if n != 2 and self.size[0] != self.size[1]:
            self.size[1], self.size[0] = self.size
        self.rotate_state += n
        self.rotate_state %= 4
        if isinstance(self, CustomElement):
            self.update_original_image()
        self.set_image_scales()
    def add_next_el(self, child, input_key, output_key, need_process=True):
        '''Вызывается когда отпускается лкм над будущим next_element'''
        '''self - first_linked'''
        '''Результат выполнения - неуспешно ли добавление'''
        if isinstance(child, SimpleElement):
            input_key = 0
            if self == child: return
        if [self, output_key] in child.ios[0][input_key]: return True

        self.ios[1][output_key][0].append([child, input_key])
        child.ios[0][input_key].append([self, output_key])

        if need_process: self.gw.process_circuit([self])
    def get_io_index_from_pos(self, mouse_pos, is_input):
        '''Возвращает индекс кликнутого io вместе с его настоящей позицией'''
        if isinstance(self, SimpleElement):
            if is_input:
                return 0
            elif self.can_connect:
                return 0

        real_pos = self.get_real_pos()
        blocksize_click_x, blocksize_click_y = [ (value - real_pos[i]) / self.gw.blocksize for i, value in enumerate(mouse_pos)]

        if self.rotate_state in [0,2]: clicked_io = int(blocksize_click_x * len(self.ios[0 if is_input else 1]) / self.size[0]) # индекс выбранного входа(0, 180)
        else: clicked_io = int(blocksize_click_y * len(self.ios[0 if is_input else 1]) / self.size[1]) # индекс выбранного входа, если повернут(90,270)

        if (not is_input and self.rotate_state == 0) or (is_input and self.rotate_state == 2):
            if int(blocksize_click_y) != 0: return
        elif (not is_input and self.rotate_state == 1) or (is_input and self.rotate_state == 3):
            if int(blocksize_click_x) != self.size[0]-1: return
        elif (not is_input and self.rotate_state == 2) or (is_input and self.rotate_state == 0):
            if int(blocksize_click_y) != self.size[1]-1: return
        elif (not is_input and self.rotate_state == 3) or (is_input and self.rotate_state == 1):
            if int(blocksize_click_x) != 0: return

        if self.rotate_state in [2,3]: clicked_io = len(self.ios[0 if is_input else 1]) - clicked_io - 1
        return clicked_io
    def get_io_pos_from_index(self, io_index, is_input):
        if isinstance(self, SimpleElement):
            return [0.5, 0.5]
        if is_input:
            if self.rotate_state == 0:
                return [io_index * self.blocks_in_input + self.half_blocks_in_input, self.size[1]-0.5]
            elif self.rotate_state == 1:
                return [0.5, io_index * self.blocks_in_input + self.half_blocks_in_input]
            elif self.rotate_state == 2:
                return [(len(self.ios[0])-io_index-1) * self.blocks_in_input + self.half_blocks_in_input, 0.5]
            else:
                return [self.size[0]-0.5, (len(self.ios[0]) - io_index - 1) * self.blocks_in_input + self.half_blocks_in_input]
        else:
            if self.rotate_state == 0:
                return [io_index * self.blocks_in_output + self.half_blocks_in_output, 0.5]
            elif self.rotate_state == 1:
                return [self.size[0]-0.5, io_index * self.blocks_in_output + self.half_blocks_in_output]
            elif self.rotate_state == 2:
                return [(len(self.ios[1])-io_index-1) * self.blocks_in_output + self.half_blocks_in_output, self.size[1]-0.5]
            else:
                return [0.5, (len(self.ios[1]) - io_index - 1) * self.blocks_in_output + self.half_blocks_in_output]
    def get_io_key_from_index(self, io_index, is_input):
        if isinstance(self, SimpleElement): return io_index
        return list(self.ios[int(not is_input)].keys())[io_index]
    def get_io_index_from_key(self, io_key, is_input):
        return list(self.ios[int(not is_input)].keys()).index(io_key)
    def to_dict(self, stay_elements_indexes):
        data = [
            [[[stay_elements_indexes[id(next_el[0])], next_el[1]] for next_el in output[0]] for output in self.ios[1].values()],
            self.x,
            self.y,
            self.rotate_state,
            ''.join(self.file_name.split('.')[:-1]) if isinstance(self, CustomElement) else AVAILABLE_ELEMENTS.index(self.__class__)
        ]
        if isinstance(self, Comment):
            data.insert(4, self.text)
        return data
    def set_lighting(self, value):
        for output_data in self.ios[1].values():
            output_data[1] = value
    def on_power_change(self):
        if hasattr(self, 'x'):
            self.set_image_scales()
    def copy(self, gw=None):
        new_el = self.__class__(self.x, self.y, gw or self.gw, self.file_name) if isinstance(self, CustomElement) else self.__class__(self.x, self.y, gw or self.gw)
        new_el.ios = [{input_name: [[id(input_data[0]) if isinstance(input_data[0], Element) else input_data[0], input_data[1]] for input_data in self.ios[0][input_name]] for input_name in self.ios[0]},
                      {output_name: [[[id(output_data[0]) if isinstance(output_data[0], Element) else output_data[0], output_data[1]] for output_data in self.ios[1][output_name][0]], False] for output_name in self.ios[1]}]
        new_el.rotate(self.rotate_state)
        if isinstance(self, Comment):
            new_el.text = self.text
        return new_el

    def __repr__(self):
        add = f' with pos: [{self.x}, {self.y}]' if hasattr(self, 'x') else str(id(self))
        return f'{self.__class__.__name__}' + add

class SimpleElement(Element):
    ''' Родительский класс всех элементов. '''
    disabled_image = None # выключенный элемент
    enabled_image = None # включённый элемент
    can_connect = True #может ли объект сам подключаться к чему-либо?
    connections = 2

    def __init__(self, *args, is_visible=True):
        # args - x, y, gw | gw
        super().__init__(*args, is_visible=is_visible)
        # [{0: [[el, el_key], ...]}, {0: [[el, el_key, ...], is_lighting]}]
        self.ios = [{0: []}, {0: [[], False]}]
        if is_visible:
            self.original_image = self.disabled_image
            self.set_image_scales()

    def is_lighting(self):
        return self.ios[1][0][1]

    def set_image_scales(self):
        if self.is_lighting(): self.original_image = self.enabled_image
        else: self.original_image = self.disabled_image

        self.image = pygame.transform.scale(pygame.transform.rotate(self.original_image, -90 * self.rotate_state), (self.gw.elements_size, self.gw.elements_size))
        if self in self.gw.selected_elements:
            pygame.draw.rect(self.image, GREEN, [0, 0, self.gw.elements_size, self.gw.elements_size], 2)
        elif self in self.gw.flying_objects:
            self.image.set_alpha(100)
        elif self == self.gw.focus_io[0]:
            pygame.draw.rect(self.image, YELLOW, [0, 0, self.gw.elements_size, self.gw.elements_size], 2)
        self.set_real_position()

class CustomElement(Element):
    font = pygame.font.SysFont(None, int(MAX_BLOCKSIZE/2.8))
    title_font = pygame.font.SysFont(None, int(MAX_BLOCKSIZE/2.2))

    def __init__(self, *args, is_visible=True):
        # args -  x, y, gw, file_name | gw, file_name
        super().__init__(*args, is_visible=is_visible)
        self.is_deleted = False # для удаления custom во время добавления, если среди inner els найден вечный цикл
        #вместе с .json, не path!
        self.file_name = args[-1]
        with open(f'{PLUGIN_CIRCUITS_PATH}{self.file_name}') as f:
            plugin_data = json.load(f)
        with open(f'{CIRCUITS_PATH}{self.file_name}') as f:
            data = json.load(f)

        # [{input_name: [[el, el_key], ...], ...}, {output_name: [[[el, el_key], ...], is_lighting], ...}]
        self.ios = [{io_name: [[], False] if bool(i) else [] for io_name in collection} for i, collection in enumerate(plugin_data)]

        was_els = {} # {el_index: el, ...}
        self.inputs = {} # el_key: el
        self.outputs = {} # el_key: el



        for input_processed_key in plugin_data[0]:
            pos = plugin_data[0][input_processed_key]
            input_processed_index = None
            for i, el_data in enumerate(data):
                if el_data[1:3] == pos:
                    input_processed_index = i
                    break

            queue = deque([[None, None, input_processed_index, None]]) # parent_index, output_key, child_index, input_key

            while queue:
                parent_index, output_key, child_index, input_key = queue.popleft()

                child_el = was_els.get(child_index)
                if not child_el:
                    el_type = data[child_index][-1]
                    child_el = AVAILABLE_ELEMENTS[el_type](self.gw, is_visible=False) if isinstance(el_type, int) else CustomElement(self.gw, el_type + '.json', is_visible=False)
                    if isinstance(child_el, ToggleSimpleElement):
                        self.inputs[input_processed_key] = child_el
                    elif isinstance(child_el, LampSimpleElement):
                        for output_lamp_key in plugin_data[1]:
                            if data[child_index][1:3] == plugin_data[1][output_lamp_key]:
                                self.outputs[output_lamp_key] = child_el
                                break

                    was_els[child_index] = child_el

                if parent_index is not None:
                    parent_el = was_els.get(parent_index)
                    if parent_el.add_next_el(child_el, input_key, output_key, False): continue

                for output_index, output_data in enumerate(data[child_index][0]):
                    for next_child in output_data:
                        queue.append([child_index, child_el.get_io_key_from_index(output_index, is_input=False), next_child[0], next_child[1]])

        can_update = []
        for el_index in range(len(data)):
            if el:=was_els.get(el_index):
                if isinstance(el, NotSimpleElement) or isinstance(el, CustomElement):
                    can_update.append(el)

        if is_visible: self.set_visible_params()

        self.gw.process_circuit(can_update, parent_custom=self)
        self.on_power_change()

    def update_original_image(self):
        BLOCKSIZE = MAX_BLOCKSIZE

        image = pygame.Surface((self.size[0] * BLOCKSIZE - 2 * GRID_OUTLINE, self.size[1] * BLOCKSIZE - 2 * GRID_OUTLINE))
        image.fill(CUSTOM_COLOR)


        text_surf = self.title_font.render(''.join(self.file_name.split('.')[:-1]), True, (255,255,255))
        text_rect = text_surf.get_rect(center=[(self.size[0] * BLOCKSIZE - 2 * GRID_OUTLINE) / 2, BLOCKSIZE])
        image.blit(text_surf, text_rect)

        for index, input_name in enumerate(self.ios[0]):
            text_surf = self.font.render(input_name, True, (255,255,255))
            io_pos = self.get_io_pos_from_index(index, is_input=True)
            text_rect = text_surf.get_rect(center=[io_pos[0] * BLOCKSIZE, io_pos[1] * BLOCKSIZE])
            image.blit(text_surf, text_rect)

        for index, output_name in enumerate(self.ios[1]):
            text_surf = self.font.render(output_name, True, (255,255,255))
            io_pos = self.get_io_pos_from_index(index, is_input=False)
            text_rect = text_surf.get_rect(center=[io_pos[0] * BLOCKSIZE, io_pos[1] * BLOCKSIZE])
            image.blit(text_surf, text_rect)
        self.original_image = image

    def set_image_scales(self):
        real_size = [self.size[0] * self.gw.blocksize - GRID_OUTLINE, self.size[1] * self.gw.blocksize - GRID_OUTLINE]
        self.image = pygame.transform.scale(self.original_image, real_size)
        if self in self.gw.selected_elements:
            pygame.draw.rect(self.image, GREEN, [0, 0, *real_size], 2)
        elif self in self.gw.flying_objects:
            self.image.set_alpha(100)
        elif self == self.gw.focus_io[0]:
            pygame.draw.rect(self.image, YELLOW, [0, 0, *real_size], 2)
        self.set_real_position()

    def set_visible_params(self):
        self.size = [max(len(self.ios[0]), len(self.ios[1])), CUSTOM_HEIGHT]
        self.blocks_in_output = self.size[0] / len(self.ios[1])
        self.half_blocks_in_output = self.blocks_in_output / 2

        self.blocks_in_input = self.size[0] / len(self.ios[0])
        self.half_blocks_in_input = self.blocks_in_input / 2
        self.update_original_image()
        self.set_image_scales()

    def on_power_change(self, parent_custom=None):
        for input_key in self.ios[0]:
            self.inputs[input_key].set_lighting(at_least_1_lighting(self, input_key))

        self.gw.process_circuit(list(self.inputs.values()), parent_custom=parent_custom or self)
        if self.is_deleted: return

        for output_key in self.outputs:
            new_value = self.outputs[output_key].is_lighting()
            self.ios[1][output_key][1] = new_value

class ToggleSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/toggle_disabled.png')
    enabled_image = pygame.image.load('images/toggle_enabled.png')
    connections = 0

    def on_click(self):
        ''' Триггер на нажатие кнопки (вкл/выкл) на верхней панели. '''
        self.set_lighting(not self.is_lighting())

class MomentarySimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/momentary_disabled.png')
    enabled_image = pygame.image.load('images/momentary_enabled.png')
    connections = 0

    def on_click(self):
        ''' Триггер на нажатие кнопки (вкл/выкл) на верхней панели. '''
        self.set_lighting(not self.is_lighting())

class LampSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/lamp_disabled.png')
    enabled_image = pygame.image.load('images/lamp_enabled.png')
    connections = math.inf
    can_connect = False

    def on_power_change(self):
        self.set_lighting(at_least_1_lighting(self, 0))
        super().on_power_change()

class AndSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/and_disabled.png')
    enabled_image = pygame.image.load('images/and_enabled.png')
    connections = math.inf
    def on_power_change(self):
        self.set_lighting( len(self.ios[0][0]) >= 2 and all(el[0].ios[1][el[1]][1] for el in self.ios[0][0]) )
        super().on_power_change()

class OrSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/or_disabled.png')
    enabled_image = pygame.image.load('images/or_enabled.png')
    connections = math.inf
    def on_power_change(self):
        self.set_lighting(at_least_1_lighting(self, 0))
        super().on_power_change()

class XorSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/xor_disabled.png')
    enabled_image = pygame.image.load('images/xor_enabled.png')

    def on_power_change(self):
        bools = [el_data[0].ios[1][el_data[1]][1] for el_data in self.ios[0][0]]
        self.set_lighting((len(bools) == 1 and bools[0]) or (len(bools) == 2 and (bools[0] ^ bools[1])))
        super().on_power_change()

class NotSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/not_enabled.png')
    enabled_image = pygame.image.load('images/not_disabled.png')
    connections = math.inf
    def __init__(self, *args, is_visible=True):
        super().__init__(*args, is_visible=is_visible)
        self.on_power_change()
    def on_power_change(self):
        self.set_lighting(not at_least_1_lighting(self, 0))
        super().on_power_change()

class LoopSimpleElement(SimpleElement):
    disabled_image = pygame.image.load('images/loop_disabled.png')
    enabled_image = pygame.image.load('images/loop_enabled.png')
    connections = math.inf
    def on_power_change(self):
        self.set_lighting(at_least_1_lighting(self, 0))
        super().on_power_change()

class Comment(SimpleElement):
    disabled_image = pygame.Surface((100, 100))
    disabled_image.fill((255,255,255))
    connections = 0
    can_connect = False
    @property
    def text(self):
        return self.__text
    @text.setter
    def text(self, value):
        self.__text = value
        self.set_image_scales()

    def set_image_scales(self):
        super().set_image_scales()
        font = pygame.font.SysFont(None, int(self.gw.blocksize/3))

        line_spacing = int(self.gw.blocksize/2.8)
        lines = (len(self.text)-1) // MAX_IO_NAME_LEN
        for i in range(lines+1):
            text_surf = font.render(self.text[i*MAX_IO_NAME_LEN:(i+1)*MAX_IO_NAME_LEN], True, (0,0,0))
            text_rect = text_surf.get_rect(center=[self.gw.blocksize_half, self.gw.blocksize_half - (lines / 2) * line_spacing + i * line_spacing ])
            self.image.blit(text_surf, text_rect)

    def __init__(self, *args, is_visible=True):
        self.__text = ''
        super().__init__(*args, is_visible=is_visible)


AVAILABLE_ELEMENTS = [ToggleSimpleElement, MomentarySimpleElement, AndSimpleElement, OrSimpleElement, XorSimpleElement, NotSimpleElement, LampSimpleElement, Comment, LoopSimpleElement]


class GameWorld:
    def __init__(self, menu, name=None):
        self.stay_elements = []
        self.camera_pos = [0, 0]
        self.selected_elements = []
        self.flying_objects = []
        self.depth = 0

        self.focus_io = [None, None, None] #io_element, io_name, is_input
        self.change_io = [None, None] #io_name, is_input

        self.carry_pos = None
        self.menu = menu
        self.is_wires_visible = True


        self.selected_line = [] # [el, index], [next_el, next_el_key] Так и должно быть!!
        self.first_linked = [] # el, io_name, logic_position

        self.blocksize = 30

        self.elements_size = self.blocksize - GRID_OUTLINE * 2
        self.blocksize_half = self.blocksize // 2
        self.logic_width = MENU_WIDTH // self.blocksize + 2
        self.logic_height = MENU_HEIGHT // self.blocksize + 2

        self.screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT), pygame.RESIZABLE)
        self.screen_rect = pygame.Rect(0, 0, MENU_WIDTH, MENU_HEIGHT)
        
        self.plugin_circuits_panel = pygame.Surface((CIRCUIT_PANEL_WIDTH, 45 * ALLOWED_IO_COUNT))
        self.plugin_circuits_panel.fill(WHITE)
        self.plugin_circuits_panel_buttons = pygame.sprite.Group()
        self.plugin_circuits_offset = [0, 0]

        self.choosing_input = False
        self.choosing_output = False
        self.add_input_btn = Button(WHITE_BUTTONSTYLE, pygame.Rect(5, 0, (CIRCUIT_PANEL_WIDTH-15)/2, 40), None, '+вход')
        self.add_output_btn = Button(WHITE_BUTTONSTYLE, pygame.Rect((CIRCUIT_PANEL_WIDTH + 5) / 2, 0, (CIRCUIT_PANEL_WIDTH-15)/2, 40), None, '+выход')
        self.add_input_btn.callback = lambda: self.add_io(self.add_input_btn, self.add_output_btn, True)
        self.add_output_btn.callback = lambda: self.add_io(self.add_output_btn, self.add_input_btn, False)

        self.plugin_circuits_panel_buttons.add(self.add_input_btn)
        self.plugin_circuits_panel_buttons.add(self.add_output_btn)



        self.inputs = {} # {io_name: [el, [changing_btn, change_btn, del_btn]], ... }
        self.outputs = {} # {io_name: [el, [changing_btn, change_btn, del_btn]], ...}
        self.renamed = {True: {}, False: {}} # True: "input_renamed" {old_name: new_name}
        self.has_io_deleted = False

        self.circuits_panel = pygame.Surface((CIRCUIT_PANEL_WIDTH, max([MENU_HEIGHT, len(os.listdir(PLUGIN_CIRCUITS_PATH)) * 45 ]) ))
        self.circuits_panel_buttons = pygame.sprite.Group()
        self.circuits_offset = [MENU_WIDTH - CIRCUIT_PANEL_WIDTH, 0]



        circuit_files = os.listdir(PLUGIN_CIRCUITS_PATH)
        if name:
            if f'{name}.json' in circuit_files: circuit_files.remove(f'{name}.json')
            updated_circuit_files = []
            file_name = name + '.json'
            for file in circuit_files:
                with open(CIRCUITS_PATH + file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for el_info in data:
                    if el_info[-1] == file_name:
                        break
                else:
                    updated_circuit_files.append(file)
        else:
            updated_circuit_files = circuit_files
        for i, file_name in enumerate(updated_circuit_files):
            if file_name == name: continue
            self.circuits_panel_buttons.add(Button(WHITE_BUTTONSTYLE, pygame.Rect(5, 5 + i * 45, CIRCUIT_PANEL_WIDTH-10, 40), lambda file_n=file_name: self.add_custom_element(file_n), ''.join(file_name.split('.')[:-1])))


        self.plugin_circuits_panel_visible = False
        self.circuits_panel_visible = False

        if not name:
            files = os.listdir(CIRCUITS_PATH)
            name = nonrepeating_name('untitled',files, i=len(files)-1, suffix='.json')
        else:
            self.load_scene(name)


        self.name = name
        self.blocksize_changed()

    def process_circuit(self, activated_elements, parent_custom=None):
        if not activated_elements: return
        counting_els = deque(activated_elements)
        processing_els = deque()
        unprocessed_parents_counter = {}
        loops = [i for i in activated_elements if isinstance(i, LoopSimpleElement)]
        while counting_els:
            el = counting_els.popleft()
            if id(el) in unprocessed_parents_counter:
                unprocessed_parents_counter[id(el)] += 1
            else:
                unprocessed_parents_counter[id(el)] = 1
                counting_els.extend([next_el[0] for output_data in el.ios[1].values() for next_el in output_data[0] if not isinstance(next_el[0], LoopSimpleElement)])
        for el in activated_elements:
            if unprocessed_parents_counter[id(el)] == 1: # не 0, потому что когда впервые добавляются дети activated_el, у него устанавливается 1(то есть кто повторяется - у того 2)
                processing_els.append(el)

        while processing_els:

            el = processing_els.popleft()
            if isinstance(el, CustomElement):
                el.on_power_change(parent_custom=parent_custom)
            elif not isinstance(el, LoopSimpleElement):
                el.on_power_change()

            for output_data in el.ios[1].values():
                for next_el in output_data[0]:
                    next_el = next_el[0]

                    if id(next_el) in unprocessed_parents_counter:
                        unprocessed_parents_counter[id(next_el)] -= 1
                        if unprocessed_parents_counter[id(next_el)] == 0 or (next_el in activated_elements and unprocessed_parents_counter[id(next_el)] == 1):
                            processing_els.append(next_el)
                    else:
                        loops.append(next_el)

        for loop_el in loops:
            previous_lighting = loop_el.is_lighting()
            loop_el.on_power_change()
            if previous_lighting != loop_el.is_lighting():
                if self.depth > 30:
                    self.depth -= 1
                    if parent_custom:
                        parent_custom.is_deleted = True
                        self.delete_elements([parent_custom])
                    else:
                        self.delete_elements(loops)
                    self.depth += 1
                    return
                else:
                    self.depth += 1
                    self.process_circuit([loop_el], parent_custom=parent_custom)
                    self.depth -= 1

    def add_custom_element(self, file_name):
        flying_object = CustomElement(0, 0, self, file_name)
        if not flying_object.is_deleted:
            self.deactivate()
            self.carry_pos = [0,0]
            flying_object.image.set_alpha(100)
            self.flying_objects.clear()
            self.flying_objects.append(flying_object)

    def save_plugin(self):
        # ["file_name", {'input_name': [x, y], ...}, {'output_name': [x, y], ...}]
        # на данный момент уже произошла чистка flying_objects в save.

        file_name = f'{PLUGIN_CIRCUITS_PATH}{self.name}.json'


        res = [{}, {}]

        for input in self.inputs:
            new_name = self.renamed[True].get(input, input)
            res[0][new_name] = [self.inputs[input][0].x, self.inputs[input][0].y]
        for output in self.outputs:
            new_name = self.renamed[False].get(output, output)
            res[1][new_name] = [self.outputs[output][0].x, self.outputs[output][0].y]


        if self.has_io_deleted:
            if not self.outputs or not self.inputs:
                if os.path.exists(file_name): os.remove(file_name)
            self.menu.on_delete_plugin(self.name)
        elif list(self.renamed[True].keys()) != list(self.renamed[True].values()) or len(self.renamed[False]) == 0:
            circuit_files = os.listdir(CIRCUITS_PATH)
            for circuit_file in circuit_files:
                with open(CIRCUITS_PATH + circuit_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for i, el_data in enumerate(data):
                    for j, output_data in enumerate(el_data[0]):
                        for k, next_el_data in enumerate(output_data):
                            if data[next_el_data[0]][-1] == self.name:
                                for old_name, new_name in self.renamed[True].items():
                                    if next_el_data and next_el_data[1] == old_name:
                                        data[i][0][j][k][1] = new_name
                                        break
                with open(CIRCUITS_PATH + circuit_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, separators=(',', ':'))

        if self.outputs and self.inputs:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(res, f, separators=(',', ':'))

    def delete_if_io(self, element):
        for index, collection in enumerate([self.outputs, self.inputs]):
            for io_name, value in collection.items():
                if element == value[0]:
                    self.delete_io(io_name, bool(index))
                    break
            else:
                continue
            break

    def save(self):
        file_name = f'{CIRCUITS_PATH}{self.name}.json'
        data = []
        stay_elements_indexes = {id(st_el): index for index, st_el in enumerate(self.stay_elements)}

        for flying_object in self.flying_objects:
            for previous_elements in flying_object.ios[0].values():
                for previous_element in previous_elements:
                    previous_element[0].ios[1][previous_element[1]][0].remove(flying_object)
            self.delete_if_io(flying_object)

        for el in self.stay_elements:
            data.append(el.to_dict(stay_elements_indexes))

        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, separators=(',', ':'))

    def load_scene(self, name):

        file_name = f'{CIRCUITS_PATH}{name}.json'

        if not os.path.exists(file_name):
            raise Exception(f'Не найдено сохранения с именем {name}')

        with open(file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)


        for el_data in data:
            if isinstance(el_data[-1], int): # если simple_element
                self.stay_elements.append(AVAILABLE_ELEMENTS[el_data[-1]](el_data[1], el_data[2], self))
            else:
                self.stay_elements.append(CustomElement(el_data[1], el_data[2], self, el_data[-1] + '.json'))

        for i_el, el_data in enumerate(data):
            el = self.stay_elements[i_el]
            el.rotate(el_data[3])
            for j_output, output_data in enumerate(el_data[0]):
                el_key = el.get_io_key_from_index(j_output, is_input=False)
                for next_el_data in output_data:
                   el.add_next_el(self.stay_elements[next_el_data[0]], next_el_data[1], el_key, False)

        can_update = []
        for i_el, el_data in enumerate(data):
            el = self.stay_elements[i_el]
            if isinstance(el, Comment):
                el.text = el_data[4]
            elif isinstance(el, NotSimpleElement) or isinstance(el, CustomElement):
                can_update.append(el)

        self.process_circuit(can_update)


        plugin_name = f'{PLUGIN_CIRCUITS_PATH}{name}.json'
        if os.path.exists(plugin_name):
            with open(plugin_name, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for index, collection in enumerate(data):
                for io_name in collection:
                    x, y = collection[io_name]
                    for el in self.stay_elements:
                        if el.x == x and el.y == y:
                            is_input = not bool(index)
                            buttons = self.add_io_button(el, is_input, name=io_name)
                            [self.inputs, self.outputs][index][io_name] = [el, buttons]
                            break

    def blocksize_changed(self):
        '''
        На zoom in / zoom out элементам всех типов изменяем размеры image
        Рисование сетки от начала экрана до конца + blocksize, запись в __grid
        '''
        self.elements_size = self.blocksize-GRID_OUTLINE*2
        self.blocksize_half = self.blocksize // 2
        for i in self.stay_elements:
            i.set_image_scales()
            i.set_real_size()
        for flying_object in self.flying_objects:
            flying_object.set_image_scales()
            flying_object.set_real_size()
        self.__grid = pygame.Surface((self.screen_rect.size[0] + self.blocksize, self.screen_rect.size[1] + self.blocksize), pygame.SRCALPHA)
        for x in range(0, self.screen_rect.size[0]+self.blocksize, self.blocksize):
            for y in range(0, self.screen_rect.size[1]+self.blocksize, self.blocksize):
                rect = pygame.Rect(x, y, self.blocksize, self.blocksize)
                pygame.draw.rect(self.__grid, WHITE, rect, GRID_OUTLINE)

    def get_pos_from_mouse(self, mouse_pos):
        '''Возвращает позицию для элемента относительно глобального нуля мира (логическую)'''
        return [(mouse_pos[i] + self.camera_pos[i]) // self.blocksize for i in range(2)]

    def get_element_from_pos(self, pos):
        for i in self.stay_elements:
            if isinstance(i, CustomElement):
                if i.x <= pos[0] <= i.x + i.size[0] - 1 and i.y <= pos[1] <= i.y + i.size[1] - 1:
                    return i
            else:
                if i.x == pos[0] and i.y == pos[1]:
                    return i

    def render(self):

        self.screen.fill((43, 43, 43))
        self.screen.blit(self.__grid, (-self.camera_pos[0] % self.blocksize - self.blocksize, -self.camera_pos[1] % self.blocksize - self.blocksize))

        positions = {id(el): el.get_real_pos() for el in self.stay_elements + self.flying_objects}
        positions_wires = {id(el): [i+self.blocksize_half for i in positions[id(el)]] for el in self.stay_elements + self.flying_objects if isinstance(el, SimpleElement)}
        if self.first_linked:
            if isinstance(self.first_linked[0], CustomElement):
                link_pos = self.first_linked[2]
                real_pos = positions.get(id(self.first_linked[0]))
                pos = [link_pos[i] * self.blocksize + real_pos[i] for i in range(2)]
            else:
                pos = positions_wires.get(id(self.first_linked[0]))
            if pos: pygame.draw.line(self.screen, WHITE, pos, pygame.mouse.get_pos(), 3)


        for flying_object in self.flying_objects:
            if self.is_wires_visible:
                if isinstance(flying_object, SimpleElement):
                    pos = positions_wires[id(flying_object)]
                else:
                    pos_ = positions[id(flying_object)]
                for i, value in enumerate(flying_object.ios[1].values()):
                    if isinstance(flying_object, CustomElement):
                        add = flying_object.get_io_pos_from_index(i, is_input=False)
                        pos = [pos_[0] + add[0] * self.blocksize, pos_[1] + add[1] * self.blocksize]
                    for el in value[0]:
                        el, input_index = el
                        if isinstance(el, CustomElement):
                            next_el_pos = el.get_io_pos_from_index(el.get_io_index_from_key(input_index, is_input=True), is_input=True)
                            next_real_pos = positions.get(id(el))
                            el_pos = [next_el_pos[i] * self.blocksize + next_real_pos[i] for i in range(2)]
                        else:
                            el_pos = positions_wires[id(el)]

                        if (line_clipped_pos:=self.screen_rect.clipline(*pos, *el_pos)):
                            pygame.draw.line(self.screen, GREEN if value[1] else WHITE, *line_clipped_pos, 3)

            self.screen.blit(flying_object.image, positions[id(flying_object)])
        if self.is_wires_visible:
            for element in self.stay_elements:
                if isinstance(element, SimpleElement):
                    output_el_pos = positions_wires[id(element)]
                else:
                    output_el_pos_real = positions.get(id(element))
                for i, output in enumerate(element.ios[1].values()):
                    is_element_in_selected = element == self.selected_line[0][0] and i == self.selected_line[0][1] if self.selected_line else False
                    if isinstance(element, CustomElement):
                        io_output_pos = element.get_io_pos_from_index(i, is_input=False)
                        output_el_pos = [io_output_pos[0] * self.blocksize + output_el_pos_real[0], io_output_pos[1] * self.blocksize + output_el_pos_real[1]]

                    for el in output[0]:
                        next_el = el[0]
                        if is_element_in_selected: is_el_in_selected = next_el == self.selected_line[1][0] and el[1] == self.selected_line[1][1]
                        if isinstance(next_el, SimpleElement):
                            input_el_pos = positions_wires[id(next_el)]
                        else:
                            input_el_pos_real = positions.get(id(next_el))
                            io_input_pos = next_el.get_io_pos_from_index(next_el.get_io_index_from_key(el[1], is_input=True), is_input=True)
                            input_el_pos = [io_input_pos[i] * self.blocksize + input_el_pos_real[i] for i in range(2)]
                        if line_clipped_pos:=self.screen_rect.clipline(*output_el_pos, *input_el_pos):
                            pygame.draw.line(self.screen, RED if is_element_in_selected and is_el_in_selected else GREEN if output[1] else WHITE, *line_clipped_pos, 3)
        for element in self.stay_elements:
            pos = positions[id(element)]
            if element.real_size[0] < pos[0] < self.screen_rect.size[0] and element.real_size[1] < pos[1] < self.screen_rect.size[1]:
                self.screen.blit(element.image, pos)


        if self.plugin_circuits_panel_visible:
            self.plugin_circuits_panel.fill(WHITE)
            self.plugin_circuits_panel_buttons.draw(self.plugin_circuits_panel)
            self.screen.blit(self.plugin_circuits_panel, (0, self.plugin_circuits_offset[1]))

        if self.circuits_panel_visible:
            self.circuits_panel.fill(WHITE)
            self.circuits_panel_buttons.draw(self.circuits_panel)
            self.screen.blit(self.circuits_panel, (self.screen_rect.size[0] - CIRCUIT_PANEL_WIDTH, self.circuits_offset[1]))


        pygame.display.update()

    def activate(self, element):
        self.carry_pos = [element.x, element.y]
        if element not in self.selected_elements:
            self.selected_elements.append(element)
        element.set_image_scales()

    def deactivate(self):
        momentaries = [el for el in self.selected_elements if isinstance(el, MomentarySimpleElement) and el.is_lighting()]
        for momentary in momentaries:
            momentary.set_lighting(False)
        self.process_circuit(momentaries)

        self.carry_pos = None
        temp_selected = self.selected_elements.copy()
        self.selected_elements.clear()
        for el in temp_selected:
            el.set_image_scales()

    def delete_elements(self, collection):
        self.carry_pos = None
        for element in collection:

            for i, input in enumerate(element.ios[0].values()):
                if not input: continue
                input_key = element.get_io_key_from_index(i, is_input=True)
                for el in input:
                    el, index = el
                    el.ios[1][index][0].remove([element, input_key])

        next_els = []

        for element in collection:
            for i, output in enumerate(element.ios[1].values()):
                if not output: continue
                output_key = element.get_io_key_from_index(i, is_input=False)
                for el in output[0]:
                    el, index = el
                    next_els.append(el)
                    el.ios[0][index].remove([element, output_key])



        for element in collection:
            if element in self.stay_elements: self.stay_elements.remove(element)
            self.delete_if_io(element)
        self.flying_objects.clear()
        self.deactivate()

        self.process_circuit(next_els)

    def get_connected_elements_at_mouse_position(self, mouse_pos):
        """Возвращает пару элементов, соединенных линией, если позиция мыши находится на линии."""

        for element in self.stay_elements:
            el_pos_ = element.get_real_pos()
            for output_index, next_elements_data in enumerate(element.ios[1].values()):
                if next_elements_data[0]:
                    add = element.get_io_pos_from_index(output_index, is_input=False)
                    el_pos = [el_pos_[0] + add[0] * self.blocksize, el_pos_[1] + add[1] * self.blocksize]
                for next_element in next_elements_data[0]:
                    next_el = next_element[0]
                    next_el_pos_ = next_el.get_real_pos()
                    next_add = next_el.get_io_pos_from_index(next_el.get_io_index_from_key(next_element[1], is_input=True), is_input=True)
                    next_el_pos = [next_el_pos_[0] + next_add[0] * self.blocksize, next_el_pos_[1] + next_add[1] * self.blocksize]

                    distance = point_to_line_distance(*mouse_pos, *el_pos, *next_el_pos)
                    if distance < 6:
                        return [element, output_index], [next_el, next_element[1]] # [el, index], [next_el, next_el_key] Так и должно быть!!

        return None, None

    def add_io(self, pressed_button, opposite_button, adding_input: bool):
        if hasattr(pressed_button, 'idle_text'): #повторный клик
            pressed_button.to_unexcited()
            if adding_input: self.choosing_input = False
            else: self.choosing_output = False
        else:
            pressed_button.to_excited(GREEN_BUTTONSTYLE, 'Выбирайте')
            opposite_button.to_unexcited()
            self.choosing_input = adding_input
            self.choosing_output = not adding_input
            self.deactivate()

    def show_io_element(self, io_name, is_input_show):
        if any(self.change_io): return
        io_elements_dict = self.inputs if is_input_show else self.outputs
        current_focus_el = io_elements_dict[io_name][0]

        old_focus_el, old_focus_name, is_input = self.focus_io
        old_io_elements_dict = self.inputs if is_input else self.outputs


        self.focus_io = [current_focus_el, io_name, is_input_show]
        if old_focus_el:
            old_io_elements_dict[old_focus_name][1][0].to_unexcited()
            old_focus_el.set_image_scales()

        if current_focus_el == old_focus_el:
            self.focus_io = [None, None, None]
            old_focus_el.set_image_scales()
            return

        io_elements_dict[io_name][1][0].to_excited(SMALL_GREEN_BUTTONSTYLE)
        current_focus_el.set_image_scales()

    def change_io_name(self, io_name, is_input_changing):

        if any(self.change_io):
            old_name, old_is_input = self.change_io
            old_io_elements_dict = self.inputs if old_is_input else self.outputs
            old_changing_btn, old_change_btn, old_del_btn = old_io_elements_dict[old_name][1]
            if list(self.renamed[old_is_input].values()).count(old_changing_btn.text) >= 1:
                new_name = nonrepeating_name(old_changing_btn.text, self.renamed[old_is_input].values())
            else:
                new_name = old_changing_btn.text
            if len(new_name) > MAX_IO_NAME_LEN or len(new_name) == 0: return
            self.change_io = [None, None]
            old_change_btn.to_unexcited()

            if old_changing_btn.idle_text == old_changing_btn.text:
                old_changing_btn.to_unexcited()
            else:
                key = [z for z in self.renamed[is_input_changing] if z == old_name][0]
                self.renamed[is_input_changing][key] = new_name

                old_changing_btn.idle_text = new_name
                old_changing_btn.to_unexcited()

        else:
            io_elements_dict = self.inputs if is_input_changing else self.outputs
            changing_btn, change_btn, _ = io_elements_dict[io_name][1]
            if any(self.focus_io):
                focus_el, focus_name, focus_is_input = self.focus_io
                focus_io_elements_dict = self.inputs if focus_is_input else self.outputs
                focus_io_elements_dict[focus_name][1][0].to_unexcited()
                self.focus_io = [None, None, None]
                focus_el.set_image_scales()
            self.change_io = [io_name, is_input_changing]
            change_btn.to_excited(SMALL_WHITE_BUTTONSTYLE, 'Сохр.')
            changing_btn.to_excited()

    def delete_io(self, io_name, is_input_deleted):
        io_elements_dict = self.inputs if is_input_deleted else self.outputs

        dlt_el, buttons = io_elements_dict[io_name]

        if dlt_el == self.focus_io[0]:
            old_focus_el = self.focus_io[0]
            self.focus_io = [None, None, None]
            old_focus_el.set_image_scales()
        elif any(self.change_io):
            change_name, change_is_input = self.change_io
            change_io_elements_dict = self.inputs if change_is_input else self.outputs
            if dlt_el == change_io_elements_dict[change_name][0]:
                self.change_io = [None, None]


        index = list(io_elements_dict.keys()).index(io_name)
        self.has_io_deleted = True
        for button in buttons:
            self.plugin_circuits_panel_buttons.remove(button)
        del io_elements_dict[io_name]
        key = [z for z in self.renamed[is_input_deleted] if z == io_name][0]
        del self.renamed[is_input_deleted][key]
        if len(io_elements_dict) < index + 1:
            return
        for buttons_on_same_lvl in [i[1] for i in list(io_elements_dict.values())[index:]]:
            for button in buttons_on_same_lvl:
                button.change_pos([button.rect.x, button.rect.y-32])

    def add_io_button(self, el, is_input, name=None):
        # Определяем начальные значения и уникальные параметры для входов и выходов
        io_elements_dict = self.inputs if is_input else self.outputs

        data_name, visible_name = name, name
        if not name:
            io_element_name_prefix = 'in' if is_input else 'out'

            if len(io_elements_dict) >= ALLOWED_IO_COUNT or el in (i[0] for i in io_elements_dict.values()): return
            data_name = nonrepeating_name(io_element_name_prefix, list(self.renamed[is_input].values()) + list(self.renamed[is_input].keys()))
            visible_name = nonrepeating_name(io_element_name_prefix, self.renamed[is_input].values())
        self.renamed[is_input][data_name] = visible_name
        start_x = 5 if is_input else CIRCUIT_PANEL_WIDTH / 2

        # Позиции и размеры кнопок
        button_height = 27
        button_spacing = 32
        start_y = len(io_elements_dict) * button_spacing + 50
        main_button_width = (CIRCUIT_PANEL_WIDTH - 15) / 4
        small_button_width = (CIRCUIT_PANEL_WIDTH - 15) / 8

        # Создаем кнопки
        main_button = Button(
            SMALL_WHITE_BUTTONSTYLE,
            pygame.Rect(start_x, start_y, main_button_width, button_height),
            lambda n=data_name, is_inp=is_input: self.show_io_element(data_name, is_input),
            visible_name
        )
        change_name_button = Button(
            SMALL_GREEN_BUTTONSTYLE,
            pygame.Rect(start_x + main_button_width + 5, start_y, small_button_width, button_height),
            lambda n=data_name, is_inp=is_input: self.change_io_name(data_name, is_input), 'Изм.'
        )
        delete_button = Button(
            SMALL_RED_BUTTONSTYLE,
            pygame.Rect(start_x + main_button_width + small_button_width + 10, start_y, small_button_width - 10, button_height),
            lambda n=data_name, is_inp=is_input: self.delete_io(data_name, is_input), 'Уд.'
        )

        # Добавляем кнопки на панель
        self.plugin_circuits_panel_buttons.add(change_name_button, main_button, delete_button)
        io_elements_dict[data_name] = [el, [main_button, change_name_button, delete_button]]

        # Сбрасываем состояние выбора
        if is_input:
            self.add_input_btn.to_unexcited()
            self.choosing_input = False
        else:
            self.add_output_btn.to_unexcited()
            self.choosing_output = False
        return main_button, change_name_button, delete_button

    def set_first_linked(self, el, mouse_pos):
        '''Вызывается когда лкм зажимаешь над объектом'''
        clicked_output = el.get_io_index_from_pos(mouse_pos, is_input=False)
        if clicked_output is None: return

        self.first_linked.append(el)
        self.first_linked.append(el.get_io_key_from_index(int(clicked_output), is_input=False))
        self.first_linked.append(el.get_io_pos_from_index(clicked_output, is_input=False))

    def main_loop(self):
        while True:
            events = pygame.event.get()

            if self.circuits_panel_visible:
                need_continue = False
                for button in self.circuits_panel_buttons:
                    if button.update(events, self.circuits_offset):
                        need_continue = True
                        break
                if need_continue: continue
            if self.plugin_circuits_panel_visible:
                for button in self.plugin_circuits_panel_buttons:
                    if button.update(events, self.plugin_circuits_offset): break

            comments = [el for el in self.selected_elements if isinstance(el, Comment)]
            printing = any(self.change_io) or (comments and len(self.selected_elements) == 1)
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                    return
                elif event.type == pygame.KEYDOWN:
                    ctrl = (pygame.key.get_mods() & pygame.KMOD_CTRL)

                    if printing:
                        is_char_delete = event.key == pygame.K_BACKSPACE

                        if any(self.change_io):
                            io_elements_dict = self.inputs if self.change_io[1] else self.outputs
                            changing_button = io_elements_dict[self.change_io[0]][1][0]
                            if is_char_delete:
                                changing_button.change_text(changing_button.text[:-1])
                            elif len(changing_button.text) < MAX_IO_NAME_LEN and ((char:=event.unicode).isalnum() or char in FILE_ACCEPTS_CHARS_APPEND):
                                changing_button.change_text(changing_button.text + char)

                        elif comments and len(self.selected_elements) == 1:
                            comment_el = comments[0]
                            if is_char_delete:
                                comment_el.text = comment_el.text[:-1]
                            elif len(comment_el.text) < MAX_IO_NAME_LEN * 3 and (char:=event.unicode).isalnum() or char in COMMENT_ACCEPTS_CHARS_APPEND:
                                comment_el.text = comment_el.text + char
                    elif pygame.K_1 <= event.key <= pygame.K_1 + len(AVAILABLE_ELEMENTS)-1:

                        self.deactivate()

                        pressed_digit = event.key - pygame.K_1

                        element = AVAILABLE_ELEMENTS[pressed_digit]
                        if element:
                            flying_object = element(0, 0, self)
                            self.carry_pos = [0,0]
                            flying_object.image.set_alpha(100)
                            self.flying_objects.clear()
                            self.flying_objects.append(flying_object)
                        else:
                            self.flying_objects.clear()
                    elif event.key == pygame.K_e:
                        for selected_element in self.selected_elements:
                            if hasattr(selected_element, 'on_click'):
                                selected_element.on_click()
                        if self.selected_elements: self.process_circuit([el for el in self.selected_elements if isinstance(el, ToggleSimpleElement) or isinstance(el, MomentarySimpleElement)])
                    elif event.key == pygame.K_i:
                        self.is_wires_visible = not self.is_wires_visible
                    elif event.key == pygame.K_r:
                        for selected_element in self.selected_elements: selected_element.rotate()
                        for flying_object in self.flying_objects: flying_object.rotate()

                    if event.key == pygame.K_DELETE or (event.key == pygame.K_q and not printing):
                        if self.selected_elements: self.delete_elements(self.selected_elements)
                        if self.selected_line:
                            el_io_info, next_el_io_info = self.selected_line
                            el, el_index = el_io_info
                            next_el, next_el_io_key = next_el_io_info
                            el_io_key = el.get_io_key_from_index(el_index, is_input=False)

                            next_el.ios[0][next_el_io_key].remove([el, el_io_key])
                            el.ios[1][el_io_key][0].remove([next_el, next_el_io_key])

                            self.selected_line.clear()
                            self.process_circuit([next_el])

                    if ctrl:
                        if event.key == pygame.K_c:
                            self.menu.copied_objects.clear()
                            if len(self.selected_elements) < 512:
                                for el in self.selected_elements:
                                    self.menu.copied_objects[id(el)] = el.copy()
                        elif event.key == pygame.K_v:
                            if self.menu.copied_objects:
                                self.flying_objects.clear()
                                self.deactivate()
                                indexes = {}
                                for key, element in self.menu.copied_objects.items():
                                    new_element = element.copy(gw=self)
                                    indexes[key] = new_element
                                for new_element in indexes.values():
                                    new_element.ios = [{input_name: [[indexes[input_data[0]], input_data[1]] for input_data in new_element.ios[0][input_name] if input_data[0] in indexes] for input_name in new_element.ios[0]},
                                                       {output_name: [[[indexes[output_data[0]], output_data[1]] for output_data in new_element.ios[1][output_name][0] if output_data[0] in indexes], False] for output_name in new_element.ios[1]}]
                                    self.flying_objects.append(new_element)
                                    new_element.image.set_alpha(100)
                                min_x = math.inf
                                min_y = math.inf


                                for el in self.flying_objects:
                                    if el.x < min_x:
                                        min_x = el.x
                                    if el.y < min_y:
                                        min_y = el.y
                                self.carry_pos = [min_x, min_y]
                                self.process_circuit([el for el in indexes.values() if not any(el.ios[0].values())])
                        elif event.key == pygame.K_TAB:
                            self.plugin_circuits_panel_visible = not self.plugin_circuits_panel_visible
                    elif event.key == pygame.K_TAB:
                        self.circuits_panel_visible = not self.circuits_panel_visible
                    elif event.key == pygame.K_ESCAPE:
                        if self.stay_elements:
                            self.save()
                            self.save_plugin()
                        else:
                            if os.path.exists(f'{CIRCUITS_PATH}{self.name}.json'): self.menu.delete_gw(self.name)
                        return

                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_e:
                        can_update = [el for el in self.selected_elements if isinstance(el, MomentarySimpleElement) and el.is_lighting()]
                        for el in can_update:
                            el.set_lighting(False)
                        self.process_circuit(can_update)
                elif event.type == pygame.MOUSEWHEEL:
                    if self.blocksize - 1 > GRID_OUTLINE*2 and event.y < 0 or self.blocksize <= MAX_BLOCKSIZE and event.y > 0:
                        blocks_in_width = (self.camera_pos[0] + self.screen_rect.size[0] // 2) // self.blocksize
                        blocks_in_height = (self.camera_pos[1] + self.screen_rect.size[1] // 2) // self.blocksize
                        self.blocksize += 1 * event.y
                        self.camera_pos[0] += blocks_in_width * event.y
                        self.camera_pos[1] += blocks_in_height * event.y

                        self.blocksize_changed()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1: #лкм
                        if self.flying_objects:
                            for flying_object in self.flying_objects:

                                if any(self.get_element_from_pos((flying_object.x + x, flying_object.y + y)) for x in range(flying_object.size[0]) for y in range(flying_object.size[1])):
                                    break
                            else:
                                for flying_object in self.flying_objects:
                                    flying_object.image.set_alpha(255)
                                    self.stay_elements.append(flying_object)

                                self.selected_elements = self.flying_objects.copy()
                                for el in self.selected_elements:
                                    el.set_image_scales()

                                self.flying_objects.clear()
                        else:
                            el = self.get_element_from_pos(self.get_pos_from_mouse(event.pos))
                            ctrl = (pygame.key.get_mods() & pygame.KMOD_CTRL)
                            el_in_selected = el and el not in self.selected_elements and not ctrl
                            el_ctrl = el or ctrl
                            if not el_ctrl or el_in_selected: # если мимо

                                self.deactivate()
                                element_io_info, next_element_io_info = self.get_connected_elements_at_mouse_position(event.pos)
                                if element_io_info:
                                    self.selected_line = [element_io_info, next_element_io_info]
                                else:
                                    self.selected_line.clear()
                            if el_ctrl: # если попал по элементу
                                # Использование функции для входов и выходов
                                if self.choosing_input and isinstance(el, ToggleSimpleElement):
                                    self.add_io_button(el, is_input=True)
                                elif self.choosing_output and isinstance(el, LampSimpleElement):
                                    self.add_io_button(el, is_input=False)
                                else:
                                    if el:
                                        if ctrl and el in self.selected_elements:
                                            self.selected_elements.remove(el)
                                            el.set_image_scales()
                                            continue
                                        self.activate(el)
                                        self.selected_line.clear()

                    elif event.button == 3:
                        if self.flying_objects:
                            self.delete_elements(self.flying_objects)

                        el = self.get_element_from_pos(self.get_pos_from_mouse(event.pos))

                        if el and (isinstance(el, CustomElement) or el.can_connect):
                            self.set_first_linked(el, event.pos)
                            self.deactivate()
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        if self.selected_elements:
                            self.carry_pos = None
                    if event.button == 3:
                        if self.first_linked:
                            el = self.get_element_from_pos(self.get_pos_from_mouse(event.pos))
                            if el:
                                was_els = set()
                                next_stack = [el]
                                while next_stack:
                                    next_el = next_stack.pop()
                                    if next_el not in was_els:
                                        if isinstance(next_el, LoopSimpleElement): continue
                                        if next_el == self.first_linked[0]: break

                                        was_els.add(next_el)

                                        next_stack += [el[0] for value in next_el.ios[1].values() for el in value[0]]
                                else:

                                    io_index = el.get_io_index_from_pos(event.pos, is_input=True)
                                    if io_index is not None:
                                        self.first_linked[0].add_next_el(el, el.get_io_key_from_index(io_index, is_input=True), self.first_linked[1])

                                        self.selected_line = [[self.first_linked[0], self.first_linked[0].get_io_index_from_key(self.first_linked[1], is_input=False)], [el, el.get_io_key_from_index(io_index, is_input=True)]]
                            self.first_linked = []
                elif event.type == pygame.MOUSEMOTION:
                    if self.selected_elements and self.carry_pos and self.get_pos_from_mouse(event.pos) != self.carry_pos:
                        carry_pos = self.carry_pos
                        for selected_element in self.selected_elements:
                            self.stay_elements.remove(selected_element)
                        self.flying_objects = self.selected_elements.copy()
                        self.deactivate()
                        self.carry_pos = carry_pos
                elif event.type == pygame.VIDEORESIZE:
                    self.screen_rect = pygame.Rect(0, 0, event.w, event.h)
                    self.circuits_offset[0] = event.w - CIRCUIT_PANEL_WIDTH
                    self.blocksize_changed()


            keys = pygame.key.get_pressed()
            if not printing:
                if keys[pygame.K_w]:  # Вверх
                    self.camera_pos[1] -= CAMERA_SPEED
                if keys[pygame.K_s]:  # Вниз
                    self.camera_pos[1] += CAMERA_SPEED
                if keys[pygame.K_a]:  # Влево
                    self.camera_pos[0] -= CAMERA_SPEED
                if keys[pygame.K_d]:  # Вправо
                    self.camera_pos[0] += CAMERA_SPEED

                elif keys[pygame.K_z] and self.blocksize <= MAX_BLOCKSIZE:
                    self.blocksize += 1
                    self.camera_pos[0] += (self.camera_pos[0] + self.screen_rect.size[0] // 2) // self.blocksize
                    self.camera_pos[1] += (self.camera_pos[1] + self.screen_rect.size[1] // 2) // self.blocksize
                    self.blocksize_changed()

                elif keys[pygame.K_x] and self.blocksize - 1 > GRID_OUTLINE*2:
                    self.blocksize -= 1
                    self.camera_pos[0] -= (self.camera_pos[0] + self.screen_rect.size[0] // 2) // self.blocksize
                    self.camera_pos[1] -= (self.camera_pos[1] + self.screen_rect.size[1] // 2) // self.blocksize
                    self.blocksize_changed()

            if keys[pygame.K_DOWN]:
                if self.circuits_offset[1] + self.circuits_panel.get_size()[1] > self.screen_rect.size[1]:
                    self.circuits_offset[1] -= CAMERA_SPEED

                if self.plugin_circuits_offset[1] + self.plugin_circuits_panel.get_size()[1] > self.screen_rect.size[1]:
                    self.plugin_circuits_offset[1] -= CAMERA_SPEED
            elif keys[pygame.K_UP]:
                if self.circuits_offset[1] < 0:
                    self.circuits_offset[1] += CAMERA_SPEED
                    self.plugin_circuits_offset[1] += CAMERA_SPEED

                if self.plugin_circuits_offset[1] < 0:
                    self.plugin_circuits_offset[1] += CAMERA_SPEED


            if self.flying_objects:
                mouse_pos_logic = self.get_pos_from_mouse(pygame.mouse.get_pos())
                for flying_object in self.flying_objects:
                    flying_object.set_pos(flying_object.x + mouse_pos_logic[0] - self.carry_pos[0], flying_object.y + mouse_pos_logic[1] - self.carry_pos[1])
                self.carry_pos = mouse_pos_logic

            self.render()

            CLOCK.tick(FPS)


class Menu:
    def __init__(self):
        self.screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT))
        self.screen_size = MENU_WIDTH, MENU_HEIGHT
        self.reset_update_name()
        self.scroll_pos = 0
        self.copied_objects = {}

        self.get_saved_gws()

    def get_saved_gws(self):

        self.panel_buttons = pygame.sprite.Group()
        self.panel_buttons.add(Button(RED_BUTTONSTYLE, pygame.Rect(MENU_WIDTH // 2 - 150, 5, 300, 40), lambda: self.choose_gw(None), 'Создать новую схему'))

        names = [f.split('.')[0] for f in os.listdir(CIRCUITS_PATH)]

        for index, name in enumerate(names):
            changing_btn = Button(WHITE_BUTTONSTYLE, pygame.Rect(MENU_WIDTH // 2 - 230, 45 * index + 50, 300, 40), lambda n=name: self.choose_gw(n), name)
            self.panel_buttons.add(changing_btn)
            change_btn = Button(GREEN_BUTTONSTYLE, pygame.Rect(MENU_WIDTH // 2 + 75, 45 * index + 50, 80, 40), None, 'Изменить')
            change_btn.callback = lambda changing_b=changing_btn, change_b=change_btn: self.name_update(changing_b,change_b)

            self.panel_buttons.add(change_btn)
            self.panel_buttons.add(Button(RED_BUTTONSTYLE, pygame.Rect(MENU_WIDTH // 2 + 160, 45 * index + 50, 80, 40), lambda n=name: self.delete_gw(n, True), 'Удалить'))
        self.panel_buttons_surface = pygame.Surface((MENU_WIDTH, 45 * (len(self.panel_buttons) // 3 + 1)), pygame.SRCALPHA)

    def reset_update_name(self):
        if hasattr(self, 'change_button'): self.change_button.to_unexcited()
        if hasattr(self, 'changing_button'): self.changing_button.to_unexcited()
        self.changing_button = None
        self.change_button = None

    def name_update(self, changing_btn, change_btn):
        is_clicked_again = self.changing_button == changing_btn
        if self.changing_button:
            if self.changing_button.text != self.changing_button.idle_text:
                #сохранить
                name = nonrepeating_name(self.changing_button.text, os.listdir(CIRCUITS_PATH), suffix='.json')
                self.changing_button.callback = lambda n=name: self.choose_gw(n)
                os.rename(f'{CIRCUITS_PATH}{self.changing_button.idle_text}.json', f'{CIRCUITS_PATH}{name}.json')

                plugin_name = f'{PLUGIN_CIRCUITS_PATH}{self.changing_button.idle_text}.json'
                if os.path.exists(plugin_name):
                    os.rename(plugin_name, f'{PLUGIN_CIRCUITS_PATH}{name}.json')

                circuit_files = os.listdir(CIRCUITS_PATH)
                for circuit_file in circuit_files:
                    with open(CIRCUITS_PATH + circuit_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    for value in data:

                        if value[-1] == self.changing_button.idle_text:
                            value[-1] = self.changing_button.text

                    with open(CIRCUITS_PATH + circuit_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, separators=(',', ':'))

                self.changing_button.change_text(name)
                self.changing_button.idle_text = name




            self.reset_update_name()
        if not is_clicked_again:
            self.change_button = change_btn
            self.change_button.to_excited( WHITE_BUTTONSTYLE, 'Сохранить')
            self.changing_button = changing_btn
            self.changing_button.to_excited()

    def choose_gw(self, name):
        if self.changing_button: self.reset_update_name()
        self.gw = GameWorld(self, name)
        self.gw.main_loop()
        self.screen = pygame.display.set_mode(self.screen_size)
        self.get_saved_gws()

    def render(self):
        self.screen.fill((43, 43, 43))
        self.panel_buttons.draw(self.panel_buttons_surface)
        self.screen.blit(self.panel_buttons_surface, (0, self.scroll_pos))
        pygame.display.update()

    def delete_gw(self, name, update=False):
        os.remove(f'{CIRCUITS_PATH}{name}.json')
        if os.path.exists(f'{PLUGIN_CIRCUITS_PATH}{name}.json'):
            os.remove(f'{PLUGIN_CIRCUITS_PATH}{name}.json')
            self.on_delete_plugin(name)
        if update: self.get_saved_gws()

    def on_delete_plugin(self, file_name):
        circuit_files = os.listdir(CIRCUITS_PATH)
        for circuit_file in circuit_files:
            with open(CIRCUITS_PATH + circuit_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            indexes = [i for i, el_data in enumerate(data) if el_data[-1] == file_name]
            for i, el_data in enumerate(data):
                if el_data[-1] == file_name:
                    del data[i]
            for el_data in data:
                for output_index, output_data in enumerate(el_data[0]):
                    next_el_index = 0
                    while next_el_index < len(output_data):
                        i = output_data[next_el_index][0]
                        minus = 0
                        for custom_index in indexes:
                            if i == custom_index:
                                del output_data[next_el_index]
                                break
                            elif i > custom_index:
                                minus += 1
                        else:
                            output_data[next_el_index][0] = i - minus
                            next_el_index+=1
            with open(CIRCUITS_PATH + circuit_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))

    def main_loop(self):
        while True:
            events = pygame.event.get()
            for panel_button in self.panel_buttons:
                if panel_button.update(events, offset=[0,self.scroll_pos]): break

            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                    return
                if event.type == pygame.KEYDOWN:
                    if self.changing_button:
                        try:
                            char = event.unicode
                            # Проверка на символы: буквы, цифры, подчеркивание, пробел
                            if char.isalnum() or char in FILE_ACCEPTS_CHARS_APPEND:
                                self.changing_button.change_text(self.changing_button.text + char)
                            elif event.key == pygame.K_BACKSPACE:
                                self.changing_button.change_text(self.changing_button.text[:-1])

                        except ValueError:
                            continue

            keys = pygame.key.get_pressed()
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                if abs(self.scroll_pos) + MENU_HEIGHT < self.panel_buttons_surface.get_size()[1]: self.scroll_pos -= MENU_CAMERA_SPEED
            elif keys[pygame.K_UP] or keys[pygame.K_w]:
                if self.scroll_pos < 0: self.scroll_pos += MENU_CAMERA_SPEED


            self.render()

            CLOCK.tick(FPS)


if __name__ == '__main__':
    menu = Menu()
    menu.main_loop()
