# -*- coding:utf-8 -*-

import pygame as pg
import sys,os,random

TEST_FLAG=False

class GridPos:
    XY=1
    RSS=2
    XYZ=3

    @staticmethod
    def fix_pos_xyz(pos_xyz:tuple[int,int,int])->tuple[int,int,int]:
        fix=min(pos_xyz)
        pos_xyz=(pos_xyz[0]-fix,pos_xyz[1]-fix,pos_xyz[2]-fix)
        # do not check if max(pos_xyz)<=5, because it may be an r=6 pos neighboring an r=5
        return pos_xyz

    @staticmethod
    def xyz2xy(pos_xyz:tuple[int,int,int])->tuple[int,int]:
        center=(401,326)
        if pos_xyz==(0,0,0): return center
        dx,dy,dz=(66,0),(-33,-57),(-33,57)
        x,y,z=pos_xyz
        dest=(center[0]+x*dx[0]+y*dy[0]+z*dz[0],
              center[1]+x*dx[1]+y*dy[1]+z*dz[1])
        return dest

    @staticmethod
    def rss2xyz(pos_rss:tuple[int,int,int])->tuple[int,int,int]:
        if pos_rss==(0,0,0): return 0,0,0
        seg_dir=((0,1,0),(-1,0,0),(0,0,1),(0,-1,0),(1,0,0),(0,0,-1))
        r,sg,st=pos_rss
        cur=(r,0,0)
        for i in range(sg):
            d=seg_dir[i]
            cur=cur[0]+r*d[0],cur[1]+r*d[1],cur[2]+r*d[2]
        d=seg_dir[sg]
        cur=cur[0]+st*d[0],cur[1]+st*d[1],cur[2]+st*d[2]
        xyz=GridPos.fix_pos_xyz(cur)
        return xyz

    @staticmethod
    def xyz2rss(pos_xyz:tuple[int,int,int])->tuple[int,int,int]:
        if pos_xyz==(0,0,0): return 0,0,0
        x,y,z=pos_xyz
        r=max(pos_xyz)
        cur=(r,0,0)
        while GridPos.rss2xyz(cur)!=pos_xyz:
            cur=cur[0],cur[1],cur[2]+1
            if cur[2]==r:
                cur=cur[0],cur[1]+1,0
                if cur[1]==6:
                    raise ValueError('XYZ2RSS_SegCountError')
        return cur

    @staticmethod
    def neighboring_pos_xyz(pos:tuple[int,int,int])->list[tuple[int,int,int]]:
        dirs=((1,0,0),(0,0,-1),(0,1,0),(-1,0,0),(0,0,1),(0,-1,0))
        return [GridPos.fix_pos_xyz((pos[0]+d[0],pos[1]+d[1],pos[2]+d[2])) for d in dirs]

    @staticmethod
    def is_free(pos_xyz:tuple[int,int,int],
                group:pg.sprite.Group)->bool:
        neighbors=GridPos.neighboring_pos_xyz(pos_xyz)
        free=[True]*6
        for atom in group:
            if atom.pos.xyz in neighbors:
                free[neighbors.index(atom.pos.xyz)]=False
            if sum(free)<=2: return False
        if sum(free)>=5: return True

        if ((free[0] and free[1] and free[2])
            or (free[1] and free[2] and free[3])
            or (free[2] and free[3] and free[4])
            or (free[3] and free[4] and free[5])
            or (free[4] and free[5] and free[0])
                or (free[5] and free[0] and free[1])):
            return True
        else:
            return False

    def __init__(self,
                 pos:tuple[int,int,int],
                 pos_format:int):
        if pos_format==self.RSS:
            self.rss=pos
            self.xyz= self.rss2xyz(pos)
        elif pos_format==self.XYZ:
            self.xyz=pos
            self.rss= self.xyz2rss(pos)
        else:
            raise ValueError('GridPosInit_FormatError')
        self.xy= self.xyz2xy(self.xyz)

    def __eq__(self,other):
        if isinstance(other,GridPos):
            return (self.rss,self.xyz,self.xy)==(other.rss,other.xyz,other.xy)
        else:
            return False

class Atom(pg.sprite.Sprite):
    TRANSPARENT=64

    def __init__(self,
                 name:str,
                 image:pg.Surface,
                 pos:tuple[int,int,int],
                 pos_format:int):
        super().__init__()
        self.name=name
        self.base_image=image.copy() # image should be un-converted
        self.image=image.copy()
        self.pos=GridPos(pos,pos_format)  # 3rd-gen: x/y/z-coordinate; 2nd-gen: r/sg/st-coordinate
        self.rect=pg.Rect(self.pos.xy,image.get_size())
        self.unlock=False
        self.selection=[False,False]
        self.selection_refreshed=[True,True]

    def update(self, *args, **kwargs):
        resources=args[0]
        # update unlock
        atom_group=self.groups()[0]
        free=GridPos.is_free(self.pos.xyz,atom_group)
        if self.name not in (metals:=('lead','tin','iron','copper','silver','gold')):
            self.unlock=free
        else:
            inferior=metals[:metals.index(self.name)]
            for each in atom_group:
                if each.name in inferior:
                    self.unlock=False
                    break
            else:
                self.unlock=free
        # update selection
        if not all(self.selection_refreshed):
            base=self.base_image.copy()
            if self.selection[1]: # RMB: labelling
                base.blit(resources['grid']['selection'][1],(0,0))
            # no need to check self.unlock for selection[0],
            # because handle_event() ensures that only free atoms can be selected
            if self.selection[0]: # LMB: selection
                base.blit(resources['grid']['selection'][0],(0,0))
            self.image=base.copy()
            self.image.set_alpha(255 if self.unlock else Atom.TRANSPARENT)
            self.selection_refreshed[1]=True
            self.selection_refreshed[0]=True
        self.image.set_alpha(255 if self.unlock else Atom.TRANSPARENT)

def read_save()->dict:
    save=dict()
    try:
        img=pg.image.load('./res/disposal.png')
    except FileNotFoundError:
        # init new save pixel
        base_img=pg.image.load('./res/grid/disposal.png')
        pg.image.save(base_img,'./res/disposal.png')
        img=pg.image.load('./res/disposal.png')
    c=img.get_at((0,0))
    save['mode']='advanced' if c[3] else 'normal'
    save['count']=c[0]*2**16+c[1]*2**8+c[2]
    return save

def init_game(save:dict)->pg.Surface:
    # load & set window size
    # no need to set icon & title, will be set in new_game()
    board=pg.image.load('./res/empty_board.png')
    main_screen=(pg.display.set_mode(size=board.get_size()))
    # load & play music
    pg.mixer.music.load('./res/music/Solitaire.ogg')
    pg.mixer.music.set_volume(0.6)
    pg.mixer.music.play(loops=-1,fade_ms=1000)
    # set cursor
    pg.mouse.set_cursor(pg.cursors.Cursor((49,49),pg.image.load('./res/cursor_normal.png').convert_alpha()))
    return main_screen

def get_resources()->dict:
    res=dict()
    res['board']=pg.image.load('./res/empty_board.png').convert()
    res['rules']=pg.image.load('./res/rules_solitaire_chn.png').convert()
    # icons
    res['icon_normal']=pg.image.load('./res/icon_normal.png').convert_alpha()
    res['icon_advanced']=pg.image.load('./res/icon_advanced.png').convert_alpha()
    # indicators
    res['indicators_normal']=pg.image.load('./res/indicators_normal.png').convert_alpha()
    res['indicators_advanced']=pg.image.load('./res/indicators_advanced.png').convert_alpha()
    # in-grid resources
    res['grid']=dict()
    res['grid']['selection']=(pg.image.load('./res/grid/selection_1.png').convert_alpha(),
                              pg.image.load('./res/grid/selection_2.png').convert_alpha())
    # atoms
    res['grid']['atoms']=dict()
    for filename in os.listdir('./res/grid/atoms/'):
        res['grid']['atoms'][filename.removesuffix('.png')]=pg.image.load(f'./res/grid/atoms/{filename}').convert_alpha()
    # fonts
    res['fonts']=dict()
    res['fonts']['winnings']=pg.font.Font('./res/fonts/HYHanBingQuW.ttf',14)
    res['fonts']['indicators']=pg.font.Font('./res/fonts/HYXuanSong35S.ttf',10)
    return res

def generate_slots_rss()->list[tuple[int,int,int]]:
    total=54
    symmetry=random.choice((2,3,6))
    # get all 90 possible slots (excluding the center)
    base_area=[]
    for r in range(1,6):
        for sg in range(6):
            for st in range(r):
                base_area.append((r,sg,st))
    # initialize
    not_chosen=base_area # RSS
    choice=random.choice(not_chosen) # RSS
    chosen=[(choice[0],(choice[1]+i)%6,choice[2]) for i in range(6) if (i*symmetry)%6==0] # RSS
    for each in chosen:
        not_chosen.remove(each)
    # filling up
    while len(chosen)<total:
        # choose a neighbor of an already-chosen atom
        # remember to convert between RSS and XYZ
        choice=random.choice(not_chosen)
        while all([(GridPos.xyz2rss(neighbor) not in chosen)
                   for neighbor in GridPos.neighboring_pos_xyz(GridPos.rss2xyz(choice))]):
            choice=random.choice(not_chosen)
        # extend with symmetry
        sym_choices=[(choice[0],(choice[1]+i)%6,choice[2]) for i in range(6) if (i*symmetry)%6==0]
        # maintenance
        for each in sym_choices:
            not_chosen.remove(each)
            chosen.append(each)

    return [(0,0,0)]+chosen

def get_atom_pool_converted(resources:dict,advanced:bool)->list:
    atoms=resources['grid']['atoms']
    # salt
    pool=[('salt',atoms['salt'])]*4
    # basics
    for element in ('air','earth','fire','water'):
        pool.extend([(element,atoms[element])]*8)
    # quicksilver
    pool.extend([('quicksilver',atoms['quicksilver'])]*5)
    # metals
    for metal in ('lead','tin','iron','copper','silver','gold'):
        pool.append((metal,atoms[metal]))
    # vitae & mors
    for each in ('vitae','mors'):
        pool.extend([(each,atoms[each])]*3)
    if advanced:
        # quintessence
        pool.extend([('quintessence',atoms['quintessence'])]*2)
    else:
        # 4th vitae & mors pair
        for each in ('vitae','mors'):
            pool.append((each,atoms[each]))
    return [(each[0],each[1].convert_alpha()) for each in pool]

def fill_atoms(atom_pool:list,atom_slots:list)->list[Atom]:
    atoms=[]
    random.shuffle(atom_pool)
    random.shuffle(atom_slots)
    gold_index=[i for i,each in enumerate(atom_pool) if each[0]=='gold'][0]
    gold_atom_tuple=atom_pool.pop(gold_index)
    center_index=[i for i,each in enumerate(atom_slots) if each==(0,0,0)][0]
    center_tuple=atom_slots.pop(center_index)
    atoms.append(Atom(name='gold',image=gold_atom_tuple[1],pos=center_tuple,pos_format=GridPos.RSS))
    for i,slot in enumerate(atom_slots):
        new_atom=Atom(name=atom_pool[i][0],image=atom_pool[i][1],pos=slot,pos_format=GridPos.RSS)
        atoms.append(new_atom)
    return sorted(atoms,key=lambda x: x.pos.rss)

def draw_atoms_on_new_game(main_screen:pg.Surface,
                           resources:dict,
                           filled_list:list[Atom])->pg.sprite.Group:
    atom_group=pg.sprite.Group()
    # generate spiral sequence
    spiral=[]
    r,sg,st=(0,0,0)
    while r<=5:
        spiral.append((r,sg,st))
        # rss increment; note that (sg,st)==(5,0) signals the need for r+=1
        # for r+=1, we use rss+=(1,0,1) for xyz+=(1,0,0)
        if r==0:
            r,sg,st=1,0,0
        elif (sg,st)==(5,0):
            st+=1
            r+=1
        else:
            st+=1
        if st>=r:
            st=0
            sg+=1
            if sg>=6:
                sg=0
    # prepare aura resource, remember to copy incase not to modify the original alpha
    aura_sf=resources['grid']['selection'][1].copy()
    aura_sf.set_alpha(80)
    # render in spiral sequence
    for i,slot in enumerate(spiral):
        # render board and already-grouped atoms
        main_screen.blit(resources['board'],(0,0))
        atom_group.draw(main_screen)
        # try search for atom on slot (==spiral[i]), then show aura in spiral[i+1]
        found=False
        # adds new atom
        for atom in filled_list:
            if atom.pos.rss==slot:
                filled_list.remove(atom)
                atom_group.add(atom)
                # update immediately
                atom_group.update(resources)
                found=True
                break
        if found:
            main_screen.blit(resources['board'],(0,0))
            atom_group.draw(main_screen)
        # show aura in spiral[i+1]
        if i+1<len(spiral):
            next_slot=spiral[i+1]
            aura_xy=GridPos.xyz2xy(GridPos.rss2xyz(next_slot))
            main_screen.blit(aura_sf,aura_xy)
        # refresh screen
        pg.display.flip()
        # wait for a short time
        pg.time.wait(25)
    return atom_group

def render_winnings(main_screen:pg.Surface,
                    resources:dict,
                    status:dict,
                    save:dict)->None:
    # should only render at the beginning of a new game, or when winning a game
    # define area: (>=x1,<x2,>=y1,<y2)
    start_x,start_y=748,733
    size_x,size_y=94,27 # bottom-right 94x27
    area=(start_x,start_x+size_x,start_y,start_y+size_y)
    winnings=save['count']
    font=resources['fonts']['winnings']
    # render to Surface
    text_sf=font.render(str(winnings),True,(0,0,0))
    ranges=text_sf.get_size()
    # calculate position
    delta=((area[1]-area[0]-ranges[0])//2,(area[3]-area[2]-ranges[1])//2)
    # display with y-fix
    main_screen.blit(text_sf,(area[0]+delta[0],area[2]+delta[1]-2))

def render_indicators(main_screen:pg.Surface,
                      atom_group:pg.sprite.Group,
                      resources:dict,
                      status:dict,
                      save:dict)->None:
    # should only render at the beginning of a new game, or when atoms got matched
    # define area: (>=x1,<x2,>=y1,<y2)
    start_x,start_y=155,703
    size_x,size_y=543,57 # bottom-center 543x57
    area=(start_x,start_x+size_x,start_y,start_y+size_y)
    # render to Surface
    base_sf=resources[f"indicators_{save['mode']}"]
    main_screen.blit(base_sf,(area[0],area[2]))
    pg.display.flip()
    # render counters
    font=resources['fonts']['indicators']
    stating_center=(25,28) # center of each atom icon
    offset=(18,-20) # offset to the top-right corner of each atom icon
    names=('salt','air','fire','water','earth',
           'quicksilver' if save['mode']=='normal' else 'quintessence')
    spacings=(0, 54, 42, 42, 42, # salt & basics
              64 if save['mode']=='normal' else 54) # quicksilver or quintessence
    for i,x in enumerate(zip(names,spacings)):
        name,spacing=x
        count=len([each for each in atom_group if each.name==name])
        text_sf=font.render(str(count),True,(255,255,255))
        ranges=text_sf.get_size()
        pos=(area[0]+stating_center[0]+offset[0]-ranges[0]//2+sum(spacings[:i+1]),
             area[2]+stating_center[1]+offset[1]-ranges[1]//2)
        # display with y-fix
        main_screen.blit(text_sf,(pos[0],pos[1]+2))
        pg.display.flip()

def new_game(main_screen:pg.Surface,
             resources:dict,
             status:dict,
             save:dict)->pg.sprite.Group:
    # reset status
    status['selected'].empty()
    flags=status['flags']
    flags['rules']=False
    flags['refresh']=False
    flags['start']=True
    flags['finished']=False
    # reset screen
    main_screen.blit(resources['board'].convert(),(0,0))
    pg.display.set_icon(resources[f"icon_{save['mode']}"])
    pg.display.set_caption(f"Sigmar's Garden [{save['mode'].capitalize()} Mode]")
    # generate slots and atoms
    atom_slots=generate_slots_rss()
    atom_pool=get_atom_pool_converted(resources,save['mode']=='advanced')
    assert len(atom_slots)==len(atom_pool)==55, 'SlotOrPoolCountError'
    # fill atoms to position
    filled_list=fill_atoms(atom_pool,atom_slots)
    # todo: TEST-ONLY, convenience for testing render logic of winning effect
    if TEST_FLAG:
        filled_list=[Atom(name='gold',image=resources['grid']['atoms']['gold'],
                          pos=(0,0,0),pos_format=GridPos.RSS),
                     Atom(name='gold',image=resources['grid']['atoms']['gold'],
                          pos=(2,0,0),pos_format=GridPos.RSS),]
    # assign group and draw atoms onto screen
    atom_group=draw_atoms_on_new_game(main_screen,resources,filled_list)
    # render indicators when game starts
    render_indicators(main_screen,atom_group,resources,status,save)
    # render winnings when game starts
    render_winnings(main_screen,resources,status,save)
    # refresh display
    pg.display.flip()
    return atom_group

def get_click_areas(main_screen:pg.Surface)->dict:
    x_max,y_max=main_screen.get_size()
    return {
        # area: (>=x1,<x2,>=y1,<y2)
        'close':(x_max-32,x_max-4,4,32), # top-right 28x28
        'new':(13,147,y_max-71,y_max-15), # bottom-left 134x56
        'rules':(x_max-155,x_max-115,y_max-71,y_max-15), # bottom-right 40x56
    }

def write_save(save:dict)->None:
    img=pg.image.load('./res/disposal.png')
    c=save['count']%2**24
    m=1 if save['mode']=='advanced' else 0
    img.set_at((0,0),(c//2**16,(c%2**16)//2**8,c%2**8,m))
    pg.image.save(img,'./res/disposal.png')

def quit_game(save:dict)->None:
    write_save(save)
    pg.quit() # must be first, for sys.exit() quits everything
    sys.exit()

def try_match(selected_group:pg.sprite.Group,
              status:dict,
              atom:Atom)->pg.sprite.Group:
    flags=status['flags']
    if atom.name=='gold':
        atom.kill()
        flags['indicators']=True # need to refresh indicators when atoms matched
        return selected_group
    # note that atom.selection[0] isn't set to True now
    # also don't need to set atom.selection_refreshed[0] to False
    pair_matches=( # each tuple sorted by alphabetical order of atom names
        ('air','air'), ('earth','earth'), ('fire','fire'), ('water','water'),
        ('air','salt'), ('earth','salt'), ('fire','salt'), ('salt','water'), ('salt','salt'),
        ('lead','quicksilver'), ('quicksilver','tin'), ('iron','quicksilver'),
        ('copper','quicksilver'), ('quicksilver','silver'), ('gold','quicksilver'),
        ('mors','vitae'),
    )
    quin_set={'air','earth','fire','water','quintessence'}
    if not selected_group:
        atom.selection[0]=True
        selected_group.add(atom)
    else:
        if len(selected_group)==1:
            pre=selected_group.sprites()[0]
            pair=tuple(sorted((pre.name,atom.name)))
            if pair in pair_matches:
                # match, remove atoms
                pre.selection[0]=False
                pre.selection_refreshed[0]=False
                pre.kill()
                atom.kill()
                flags['indicators']=True # need to refresh indicators when atoms matched
            elif pair.count('quintessence')==1 and set(pair).issubset(quin_set):
                # adds selection
                atom.selection[0]=True
                atom.selection_refreshed[0]=False
                selected_group.add(atom)
            else:
                # unmatch, change selection focus
                pre.selection[0]=False
                pre.selection_refreshed[0]=False
                selected_group.remove(pre)
                atom.selection[0]=True
                selected_group.add(atom)
        else:
            # multiple atoms selected, can only be quin_set, or change an element choice
            combined=set([each.name for each in selected_group]+[atom.name])
            # match and remove
            if combined==quin_set:
                for each in selected_group:
                    each.selection[0]=False
                    each.selection_refreshed[0]=False
                    each.kill()
                atom.kill()
                flags['indicators']=True # need to refresh indicators when atoms matched
            elif combined.issubset(quin_set):
                # adds selection
                if len(combined)>len(selected_group):
                    atom.selection[0]=True
                    atom.selection_refreshed[0]=False
                    selected_group.add(atom)
                # change a selected type of basic element
                else:
                    pre=[each for each in selected_group if each.name==atom.name][0]
                    # remove previous
                    pre.selection[0]=False
                    pre.selection_refreshed[0]=False
                    selected_group.remove(pre)
                    # adds new
                    atom.selection[0]=True
                    atom.selection_refreshed[0]=False
                    selected_group.add(atom)
            else:
                # unmatch, change selection focus
                for each in selected_group:
                    each.selection[0]=False
                    each.selection_refreshed[0]=False
                    selected_group.remove(each)
                atom.selection[0]=True
                atom.selection_refreshed[0]=False
                selected_group.add(atom)
    return selected_group

def handle_event(event:pg.event.Event,
                 main_screen:pg.Surface,
                 resources:dict,
                 atom_group:pg.sprite.Group,
                 status:dict,
                 save:dict)->pg.sprite.Group:
    click_areas=get_click_areas(main_screen)
    flags=status['flags']
    if event.type==pg.KEYDOWN:
        if event.key==pg.K_ESCAPE:
            if flags['rules']:
                flags['rules']=False
                flags['refresh']=True
            else:
                quit_game(save)
        elif event.key==pg.K_r:
            flags['rules']=not flags['rules']
            flags['refresh']=True
        elif event.key==pg.K_n:
            return new_game(main_screen,resources,status,save)
        elif event.key==pg.K_m:
            save['mode']='advanced' if save['mode']=='normal' else 'normal'
            return new_game(main_screen,resources,status,save)
    elif event.type==pg.MOUSEBUTTONDOWN:
        click_pos,click_button=event.dict['pos'],event.dict['button']
        # check click areas
        close=click_areas['close']
        new=click_areas['new']
        rules=click_areas['rules']
        if close[0]<=click_pos[0]<close[1] and close[2]<=click_pos[1]<close[3]:
            # quits rules explanation or quits game
            if flags['rules']:
                flags['rules']=False
                flags['refresh']=True
            else:
                quit_game(save)
        elif new[0]<=click_pos[0]<new[1] and new[2]<=click_pos[1]<new[3]:
            return new_game(main_screen,resources,status,save)
        elif rules[0]<=click_pos[0]<rules[1] and rules[2]<=click_pos[1]<rules[3]:
            flags['rules']=True
            flags['refresh']=True
        elif not flags['finished']:
            # check if click on an atom
            for atom in atom_group:
                if atom.rect.collidepoint(click_pos):
                    # first check game mode change
                    if flags['start']:
                        flags['start']=False
                        if click_button==1 and atom.name=='gold' and atom.pos.rss==(0,0,0):
                            save['mode']='advanced' if save['mode']=='normal' else 'normal'
                            return new_game(main_screen,resources,status,save)
                    # left-click: selection
                    if click_button==1:
                        # previous selection status
                        pre=atom.selection[0]
                        if atom.unlock and not atom.selection[0]:
                            status['selected']=try_match(status['selected'],status,atom)
                        else:
                            # unselect
                            atom.selection[0]=False
                            status['selected'].remove(atom)
                        # flag selection refresh
                        if pre!=atom.selection[0]:
                            atom.selection_refreshed[0]=False
                        flags['refresh']=True # need to refresh screen when atom selection changes
                    # right-click: labelling
                    elif click_button==3:
                        pre=atom.selection[1]
                        atom.selection[1]=not atom.selection[1]
                        if pre!=atom.selection[1]:
                            atom.selection_refreshed[1]=False
                        flags['refresh']=True # need to refresh screen when atom selection changes
                    # breaks loop, even if atom clicked by some other mouse button
                    break
    return atom_group

def refresh_screen(main_screen:pg.Surface,
                   atom_group:pg.sprite.Group,
                   resources:dict,
                   status:dict,
                   save:dict)->pg.Surface:
    flags=status['flags']
    pre=flags['finished']
    if flags['rules']:
        # showing rules, game unfinished
        if main_screen.get_size()!=resources['rules'].get_size():
            main_screen=pg.display.set_mode(size=resources['rules'].get_size())
        main_screen.blit(resources['rules'],(0,0))
        flags['finished']=False
    elif flags['refresh']:
        flags['refresh']=False
        # showing game
        if main_screen.get_size()!=resources['board'].get_size():
            main_screen=pg.display.set_mode(size=resources['board'].get_size())
        main_screen.blit(resources['board'],(0,0))
        # check if all cleared (won the game)
        atom_group.update(resources)
        flags['finished']=True if not atom_group else False
        # refresh atoms display
        atom_group.draw(main_screen)
        # render indicators
        render_indicators(main_screen,atom_group,resources,status,save)
        # add to count when successfully winning a game
        if flags['finished'] and not pre:
            save['count']+=1
            # todo: TEST-ONLY, allowing setting winning counts
            if TEST_FLAG:
                print(f"Winning count: {save['count']}")
                rs=input('Reset winning count ?= ')
                if rs: save['count']=int(rs)
        # render winnings
        render_winnings(main_screen,resources,status,save)
        # render winning effects
        if flags['finished'] and not pre:
            pattern=resources['grid']['selection'][1].copy()
            pattern.set_alpha(80)
            # render by r increment
            for r in range(5+1):
                main_screen.blit(resources['board'],(0,0))
                render_winnings(main_screen,resources,status,save)
                ring=([(0,0,0)] if r==0
                      else [(r,sg,st) for st in range(r) for sg in range(6)])
                for grid in ring:
                    xy=GridPos.xyz2xy(GridPos.rss2xyz(grid))
                    main_screen.blit(pattern,xy)
                pg.display.flip()
                pg.time.wait(150)
            main_screen.blit(resources['board'],(0,0))
            render_winnings(main_screen,resources,status,save)
    # refresh display
    pg.display.flip()
    return main_screen

def main():
    pg.init()
    # reads save
    save=read_save()
    # initialize
    os.environ['SDL_VIDEO_CENTERED']='1'
    status={'selected':pg.sprite.Group(),
            'flags':dict()} # will be further added in new_game()
    main_screen=init_game(save)
    resources=get_resources()
    atom_group=new_game(main_screen,resources,status,save)
    # event loop
    clock=pg.time.Clock()
    while True:
        for event in pg.event.get():
            if event.type==pg.QUIT:
                quit_game(save)
            elif event.type!=pg.MOUSEMOTION:
                atom_group=handle_event(event,main_screen,resources,atom_group,status,save)
        main_screen=refresh_screen(main_screen,atom_group,resources,status,save)
        clock.tick(60)

def bitshift_rotation(direction:str,value:int,shift:int)->int:
    l=8
    if direction=='left':
        return ((value<<shift)|(value>>(l-shift)))&(2**l-1)
    elif direction=='right':
        return ((value>>shift)|(value<<(l-shift)))&(2**l-1)

def save_crash_file(s:str)->None:
    from datetime import datetime as dt
    from base64 import b64encode
    s=b64encode(s.encode('utf-8'),b'?!')
    ss=[]
    for i,byte_value in enumerate(s):
        ss.append(bitshift_rotation(direction='right',value=byte_value,shift=i%8))
    with open(f"./crash/{dt.now().strftime('%Y-%m-%d_%H-%M-%S.crash')}",'wb') as crash_file:
        crash_file.write(bytes(ss))

def decrypt_crash_file(filename:str)->None:
    from base64 import b64decode
    with open(filename,'rb') as crash_file:
        ss=crash_file.read()
    s=''
    for i,byte_value in enumerate(ss):
        s+=chr(bitshift_rotation(direction='left',value=byte_value,shift=i%8))
    s=b64decode(s.encode('utf-8'),b'?!')
    with open(filename,'wb') as decrypted_file:
        decrypted_file.write(s)

if __name__=='__main__':
    try:
        TEST_FLAG=bool(input('*** TEST MODE ?= '))
        main()
    except (SystemExit,KeyboardInterrupt): pass
    except:
        from traceback import print_exc,format_exc
        pg.quit()
        try: os.mkdir('./crash/')
        except FileExistsError: pass
        save_crash_file(format_exc())
        print_exc()
    finally:
        import os
        if os.path.exists('./xxx/'):
            for filename in os.listdir('./xxx/'):
                if filename.endswith('.crash'):
                    decrypt_crash_file(f'./xxx/{filename}')
        sys.exit()
