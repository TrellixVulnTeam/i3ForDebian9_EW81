#!/bin/bash
workPath="$HOME/i3ForDebian9"
# 打印字符*
function print_dot() {
  #statements
  echo
  for (( i = 0; i < 80; i++ )); do
    #statements
    echo -en "\033[33m*\033[0m"
  done
  echo
  echo
}

function print_dash() {
    echo
    for (( i = 0; i < 80; i++ )); do
        echo -en "\033[33m-\033[0m"
    done
    echo
    echo
}

function print_info() {
    print_dot
    echo "$1"
    print_dot
}

# 创建脚本工作时的临时目录
function installCache() {
  #statements
  if [[ -d "$workPath/.cache" ]]; then
    #statements
    sudo rm -rf $workPath/.cache
  fi
  mkdir -p $workPath/.cache
  cd $workPath/.cache
}

function commandSuccess() {
    if [ $1 -eq 0 ] ;then
        print_dash
        echo -e "\033[32m $2  Successful !  \033[0m"
        print_dash
    else
        print_dash
        echo -e "\033[31m $2  Failed !!!  \033[0m"
        print_dash
        exit
    fi
}

function installApplications() {
  #statements
  sudo apt -y update
  sudo apt -y install lightdm i3 git vim neofetch feh resolvconf \
      fonts-wqy-zenhei lxappearance gdebi qt4-qtconfig compton \
      curl wget ranger volumeicon-alsa alsa-utils pulseaudio \
      pavucontrol fonts-arphic-uming arandr xdg-utils \
      wpasupplicant htop p7zip-full xfce4-terminal \
      xfce4-notifyd zsh xfce4-power-manager* thunar \
      breeze-cursor-theme file-roller pulseaudio-module-bluetooth \
      blueman rofi xbindkeys zsh-syntax-highlighting scrot \
      imagemagick zathura* tk parcellite network-manager network-manager-gnome \
      mesa* gpick menulibre aptitude
  commandSuccess $? "Base applications Installation "
}

function someNeedsApplications() {
  #statements
  # 安装 fcitx 输入法支持
  sudo apt -y install fcitx fcitx-data fcitx-frontend-qt4 \
      fcitx-libs-qt fcitx-module-x11 fcitx-bin fcitx-frontend-all \
      fcitx-frontend-qt5 fcitx-table fcitx-config-common \
      fcitx-frontend-fbterm fcitx-libs fcitx-module-dbus \
      fcitx-table-wubi fcitx-config-gtk fcitx-frontend-gtk2 \
      fcitx-libs-dev fcitx-module-kimpanel fcitx-ui-classic \
      fcitx-config-gtk2 fcitx-frontend-gtk3 fcitx-modules
  commandSuccess $? "Fcitx Installation "
  # 安装 telegram , Chrome , sogoupinyin , Atom , VSCode
  sudo apt -y update
  sudo apt -y install telegram-desktop google-chrome-stable \
      sogoupinyin atom code numix-gtk-theme numix-icon-theme
  commandSuccess $? "Some needs applications Installation "
  # 卸载 dunst ,因为它与 xfce4-notifyd 会发生冲突
  # 卸载 NetworkManager
  sudo apt -y purge dunst notification-daemon
}

function installLightdmWebKit2() {
  #statements
  installCache
  echo 'deb http://download.opensuse.org/repositories/home:/antergos/Debian_9.0/ /' | sudo tee /etc/apt/sources.list.d/home:antergos.list
  # wget -nv https://download.opensuse.org/repositories/home:antergos/Debian_9.0/Release.key -O Release.key
  sudo apt-key add - < $workPath/ReleaseKey/Release.key
  sudo apt -y update
#  sudo apt -y install lightdm-webkit2-greeter
  sudo gdebi -n $workPath/lightdmWebKit2Greeter/lightdm-webkit2-greeter_2.2.5-1+15.2_amd64.deb
  commandSuccess $? "Lightdm-WebKit2-Greeter Installation "

  # 更改默认ubuntu默认的unity-greeter为lightdm-webkit2-greeter
  sudo sed -i '/#greeter-session=example-gtk-gnome/agreeter-session=lightdm-webkit2-greeter' /etc/lightdm/lightdm.conf
  # 更换"lightdm-webkit2-greeter"主题为aether
  sudo cp -rf $workPath/Aether /usr/share/lightdm-webkit/themes/lightdm-webkit-theme-aether
  sudo sed -i 's/^webkit_theme\s*=\s*\(.*\)/webkit_theme = lightdm-webkit-theme-aether #\1/g' /etc/lightdm/lightdm-webkit2-greeter.conf
}

function installGrub2Themes() {
  #statements
  # 更改Grub2主题
  sudo mkdir -p /boot/grub/themes
  sudo cp -rf $workPath/grub2-themes/* /boot/grub/themes
  sudo grep "GRUB_THEME=" /etc/default/grub 2>&1 >/dev/null && sudo sed -i '/GRUB_THEME=/d' /etc/default/grub
  echo "GRUB_THEME=\"/boot/grub/themes/Vimix/theme.txt\"" | sudo tee -a /etc/default/grub
  sudo update-grub
  commandSuccess $? "Set Grub themes "
}

function installOsxArcThemes() {
  #statements
  sudo gdebi -n $workPath/osx-arc/osx-arc*.deb
  commandSuccess $? "Osx-arc Gtk3 Themes "
}

function installOhMyZsh() {
  #statements
  # 安装ohmyzsh
  cd $HOME
  sh -c "$(wget https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh -O -)"
  # 安装zsh-autosuggestions
  git clone https://github.com/zsh-users/zsh-autosuggestions ~/.zsh/zsh-autosuggestions
  installCache
}

function configDNS() {
  #statements
  # 添加 DNS
  echo "Configure DNS"
  cat <<DNS_RESOLV_CONF | sudo tee /etc/resolvconf/resolv.conf.d/head
nameserver 223.5.5.5
nameserver 8.8.8.8
DNS_RESOLV_CONF
  sudo resolvconf -u &&  sudo resolvconf --enable-updates
  commandSuccess $? "DNS setting "
}

function installFonts() {
  #statements
# 安装字体以及字体配置
  installCache
  bash $workPath/fonts/fonts-master/install.sh
  sudo cp -rf $workPath/fonts/noto* /usr/share/fonts/truetype/
  sudo cp -rf $workPath/fonts/fontConfig/66-noto* /etc/fonts/conf.avail/
  # wget -c https://raw.githubusercontent.com/ohmyarch/fontconfig-zh-cn/master/fonts.conf
  mkdir -p $HOME/.config/fontconfig
  mkdir -p $HOME/.local/share/fonts
  mkdir -p $HOME/.config/fontconfig/conf.d
  cp -rf $workPath/fonts/fontConfig/fonts.conf $HOME/.config/fontconfig
  rm -rf $HOME/.config/fontconfig/conf.d/10-powerline-symbols.conf
  cp -rf $workPath/fonts/fontConfig/10-powerline-symbols.conf $HOME/.config/fontconfig/conf.d
  cp -rf $workPath/fonts/Mesl* $HOME/.local/share/fonts
  cp -rf $workPath/fonts/myfonts $HOME/.local/share/fonts
  cp -rf $workPath/fonts/fontawesome $HOME/.local/share/fonts
  sudo chown root:root /usr/share/fonts/truetype/noto
  sudo chown root:root /usr/share/fonts/truetype/noto-cjk
  cd /usr/share/fonts/truetype/noto
  sudo chmod 644 *
  sudo chown root:root *
  cd /usr/share/fonts/truetype/noto-cjk
  sudo chmod 644 *
  sudo chown root:root *
  sudo chmod 644 /etc/fonts/conf.avail/66-noto*
  sudo chown root:root /etc/fonts/conf.avail/66-noto*
  # 更新字体缓存
  print_info "Fonts installed , Updating font cache . "
  sudo fc-cache --force --verbose
  commandSuccess $? "Fonts "
  # 生成 XDG_HOME_CONFIG
  xdg-user-dirs-update
  sudo dpkg-reconfigure locales
  sudo sed -i 's/LANGUAGE="en_US:en"/LANGUAGE="zh_CN"/g' /etc/default/locale
  installCache
}

function installProxyChains() {
  #statements
  installCache
  cp -rf $workPath/proxychains-ng $workPath/.cache
  sudo apt -y install build-essential
  cd proxychains-ng
  ./configure --prefix=/usr --sysconfdir=/etc
  make
  sudo make install
  commandSuccess $? "ProxyChains "
  sudo make install-config
  commandSuccess $? "ProxyChains config "
  # 配置 proxychains.conf . 默认端口改为 1088 . 请自行修改为自己节点设置的端口
  sudo sed -i 's/socks4 	127.0.0.1 9050/socks5  127.0.0.1 1088/g' /etc/proxychains.conf
}

function installShadowsocksr() {
  #statements
  sudo apt install libsodium23
  cp -rf $workPath/shadowsocksr $HOME
  commandSuccess $? "Shadowsocksr "
  # 请自行添加名为 config.json 的配置文件到 ~/ssconfig目录中
  cp -rf $workPath/ssconfig $HOME
  commandSuccess $? "Shadowsocksr Config "
}

function installI3Gaps() {
  #statements
  installCache
  # 安装依赖
  sudo apt -y install libxcb-keysyms1-dev libpango1.0-dev libxcb-util0-dev xcb \
                                  libxcb1-dev libxcb-icccm4-dev libyajl-dev libev-dev libxcb-xkb-dev \
                                  libxcb-cursor-dev libxkbcommon-dev libxcb-xinerama0-dev \
                                  libxkbcommon-x11-dev libstartup-notification0-dev \
                                  libxcb-randr0-dev libxcb-xrm0 libxcb-xrm-dev
  commandSuccess $? "i3Gaps needs depends Installation "
    cp -rf $workPath/i3-gaps/i3-gaps.tar.gz $workPath/.cache && tar -zxvf i3-gaps.tar.gz
    # git clone https://www.github.com/Airblader/i3 $workPath/.cache/i3-gaps
    cd $workPath/.cache/i3-gaps
    # compile & install
    autoreconf --force --install
    rm -rf build/
    mkdir -p build && cd build/
    # Disabling sanitizers is important for release versions!
    # The prefix and sysconfdir are, obviously, dependent on the distribution.
    ../configure --prefix=/usr --sysconfdir=/etc --disable-sanitizers
    make -j8
    sudo make install
    commandSuccess $? "i3Gaps Installation "
}

function installPolybar() {
  #statements
  installCache
  # 安装 依赖
  sudo apt -y install cmake cmake-data libcairo2-dev libxcb1-dev libxcb-ewmh-dev \
      libxcb-icccm4-dev libxcb-image0-dev libxcb-randr0-dev libxcb-util0-dev \
      libxcb-xkb-dev pkg-config python-xcbgen xcb-proto libxcb-xrm-dev i3-wm \
      libjsoncpp-dev libasound2-dev libpulse-dev libmpdclient-dev \
      libiw-dev libcurl4-openssl-dev libxcb-cursor-dev
  commandSuccess $? "Polybar needs depends Installation "
  print_info "Due to upstream xcbgen issues , Need xcbgen <= 12.1 , Now remove xcbgen >= 12.1 version . Install xcbgen <= 12.1 deb ."
  sudo apt -y remove --purge python-xcbgen xcb-proto
  commandSuccess $? "Xcbgen >= 13.1 removed . "
  sudo gdebi -n $workPath/polybar/xcb-proto_1.12-1_all.deb && sudo gdebi -n $workPath/polybar/python-xcbgen_1.12-1_all.deb
  commandSuccess $? "Xcbgen <= 12.1 Installed . "
  cp -rf $workPath/polybar/polybar.tar.gz $workPath/.cache
  tar -zxvf polybar.tar.gz
  mkdir polybar/build
  cd polybar/build
  cmake ..
  sudo make install
  commandSuccess $? "Polybar Installation "
  make userconfig
  commandSuccess $? "Polybar Config Installation "
}

function installMpdNcmpcpp() {
  #statements
  # 尝试删除旧的安装包 (如果存在)
  sudo apt -y remove --purge mpd ncmpcpp && sudo apt -y autoremove
  sudo rm -rf /etc/mpd.conf
  sudo rm -rf $HOME/.config/mpd
  sudo rm -rf $HOME/.mpd
  # 安装 mpd ncmpcpp
  sudo apt -y install mpd ncmpcpp
  commandSuccess $? "Mpd and Ncmpcpp Installation "
  sudo systemctl stop mpd
  sudo systemctl disable mpd
  sudo rm -rf /etc/mpd.conf
  # 配置 mpd ncmpcpp 需要的目录或文件
  mkdir -p $HOME/.mpd/playlists
  sudo cp -rf $workPath/mpd_ncmpcpp/mpd.conf $HOME/.mpd
  touch $HOME/.mpd/{mpd.db,mpd.log,mpd.pid,mpdstate}
  # 移动 ncmpcpp 的配置文件到 XDG_HOME_CONFIG
  cp -rf $workPath/mpd_ncmpcpp/.ncmpcpp $HOME
  sudo usermod -aG pulse,pulse-access mpd
  commandSuccess $? "Mpd and Ncmpcpp configure "
}

function installVimPlus() {
  #statements
  # Delete old files . if has .
  rm -rf $HOME/.vim
  rm -rf $HOME/.vimrc
  rm -rf $HOME/.vimrc.local
  rm -rf $HOME/.ycm_extra_conf.py
  mkdir -p $HOME/.vim
  # 复制文件
  cp -rf $workPath/vimConfig/* $HOME/.vim/
  cp -rf $workPath/vimConfig/.vimrc $HOME/.vim/
  cp -rf $workPath/vimConfig/.vimrc.local $HOME/.vim/
  cp -rf $workPath/vimConfig/.ycm_extra_conf.py $HOME/.vim/
  cp -rf $HOME/.vim/.vimrc $HOME
  cp -rf $HOME/.vim/.vimrc.local $HOME
  cp -rf $HOME/.vim/.ycm_extra_conf.py $HOME
  # git clone https://github.com/VundleVim/Vundle.vim.git $HOME/.vim/bundle/Vundle.vim
  # 安装编译 YCM 所需依赖
  sudo apt-get install -y ctags build-essential cmake python-dev python3-dev vim-nox
  commandSuccess $? "VimPlus , YCM depends Installation "
  # 解压 bundle 文件
  cd $HOME/.vim && tar -zxvf bundle.tar.gz
  # 编译安装 YCM
  cp -rf $workPath/YouCompleteMe $HOME/.vim/bundle
  cd $HOME/.vim/bundle/YouCompleteMe
  sudo ./install.py --clang-completer
  vim -c "PluginInstall" -c "q" -c "q"
  commandSuccess $? "Vim Plugin Installation "
  # 改变一些文件、文件夹属组和用户关系
  who_is=$(who)
  current_user=${who_is%% *}
  sudo chown -R ${current_user}:${current_user} ~/.vim
  sudo chown -R ${current_user}:${current_user} ~/.cache
  # sudo chown ${current_user}:${current_user} ~/.vimrc
  sudo chown ${current_user}:${current_user} ~/.vimrc.local
  sudo chown ${current_user}:${current_user} ~/.viminfo
  # sudo chown ${current_user}:${current_user} ~/.ycm_extra_conf.py
  # 删除 bundle.tar.gz
  rm -rf $HOME/.vim/bundle.tar.gz
  installCache
}

function installBluetooth() {
  #statements
  # 安装蓝牙驱动,这不适合所有用户
    print_info "Install Bluetooth driver , Only applies to BCM94352HMB device."
    echo
    echo -en "\033[33m Your Bluetooth device is BCM94352HMB ? Input:  ( y or other ) \033[0m"
    read action
    case $action in
      y )
       sudo cp -rf $workPath/bluetooth/BCM207*.hcd /lib/firmware/brcm
       commandSuccess $? "Bcm 94352 HMB Bluetooth device driver Installation "
       echo -e "\033[33m  Update your system , Remove not software. \033[0m"
       sudo apt -y update && sudo apt -y upgrade && sudo apt -y autoremove
       echo
       print_info "Install script is successful . 5 sec after Reboot system."
       echo
       sleep 5
       sudo reboot
        ;;
      * )
      echo -e "\033[33m  Update your system , Remove not software. \033[0m"
      sudo apt -y update && sudo apt -y upgrade && sudo apt -y autoremove
      echo
      print_info "Install script is successful . 5 sec after Reboot system."
      echo
      sleep 5
      sudo reboot
        ;;
    esac
}

function installGkSudo() {
  #statements
  sudo gdebi -n $workPath/gksudoPkg/libgtop2-7*.deb
  sudo gdebi -n $workPath/gksudoPkg/libgksu2-0_2*.deb
  sudo gdebi -n $workPath/gksudoPkg/gksu_2*.deb
  commandSuccess $? "Gksudo Installation "
}

function someConfigure() {
  #statements
  # 更改默认shell为zsh
  chsh -s /usr/bin/zsh
  # 创建未重启没有自动创建的文件夹
  mkdir -p $HOME/.config/i3
  cp -rf $workPath/.zshrc $HOME
  # 移动壁纸到家目录
  cp -rf $workPath/.wallpaper.png $HOME
  # 移动头像到家目录
  cp -rf $workPath/.face $HOME
  # 配置并加载 .Xresources
  cp -rf $workPath/.Xresources $HOME
  xrdb -merge $HOME/.Xresources
  # 移动音频文件到 Music
  cp -rf $workPath/stay.mp3 $HOME/Music
  # 移动 compton 配置文件到 ~/.config
  cp -rf $workPath/compton/compton.conf $HOME/.config/
  # 添加并配置 xbindkeys 配置文件
  cp -rf $workPath/.xbindkeysrc $HOME
  # 添加并配置 xfce4 terminal 和 thunar 等配置
  cp -rf $workPath/xfce4 $HOME/.config
  # 添加并配置通知主题配置文件
  # cp -rf $workPath/xfce4-notifyd-theme.rc $HOME/.cache
  # 设置通知主题字体
  # sudo sed -i '30 afont_name = "STXingkai 12"' /usr/share/themes/OSX-Arc-Shadow/xfce-notify-4.0/gtkrc
  # sudo sed -i "31 s/^/  / " /usr/share/themes/OSX-Arc-Shadow/xfce-notify-4.0/gtkrc
  # sudo sed -i '43 s/Bold/STXingkai 14/g' /usr/share/themes/OSX-Arc-Shadow/xfce-notify-4.0/gtkrc
  # 添加并配置 i3 配置文件
  # mv $HOME/.config/i3/config $HOME/.config/i3/config.bak
  cp -rf $workPath/i3config/* $HOME/.config/i3/
  # 给 i3 第一个工作区分配显示器
  # DIS_MONITOR=$(xrandr | grep "connected primary [0-9]" | cut -d' ' -f 1)
  # sed -i "/# workspace \$tag1 output LVDS-1/iworkspace \$tag1 output $DIS_MONITOR" $HOME/.config/i3/config
  # 添加并配置 Polybar 配置文件
  cp -rf $workPath/polybarconf/* $HOME/.config/polybar/
  # 添加当前用户名到 $HOME/.config/polybar/script/updateSoftWareAndSystem.sh
  sed -i "s/    userHome=limo/    userHome=$USER/g" $HOME/.config/polybar/script/updateSoftWareAndSystem.sh
  # 移动文件并设置开机自动启动更新软件包计时器
  sudo cp -rf $workPath/updateSystemSoftware/update-software.* /etc/systemd/system/
  sudo systemctl enable update-software.timer
  # qt4 配置文件
  cp -rf $workPath/qt4Config/* $HOME/.config
  # 添加并配置 GTK 主题配置
  cp -rf $workPath/gtk-2.0 $HOME/.config
  cp -rf $workPath/gtk-3.0 $HOME/.config
  cp -rf $workPath/.gtkrc-2.0 $HOME
  # 对于一些GUI程序无法弹出需要 gksudo的窗口,这或许有用
  sudo sed -i '4 asession required pam_loginuid.so' /etc/pam.d/lightdm
  sudo sed -i '5 asession required pam_systemd.so' /etc/pam.d/lightdm
  # 解除 nm-applet 显示设备未托管
  sudo sed -i 's/^managed=false/managed=true/' /etc/NetworkManager/NetworkManager.conf
}

function main() {
  #statements
  # 安装需要的软件
  print_info "Install base software "
  installApplications
  # 安装其他需要的软件
  print_info "Install some needs applications "
  someNeedsApplications
  # 安装 LightdmWebKit2 和 主题
  print_info "Install Lightdm-Web-Kit2 and Themes "
  installLightdmWebKit2
  # 安装 Grub2 主题
  print_info "Install Grub2 Themes "
  installGrub2Themes
  # 安装 OSX-arc GTK 主题
  print_info "Install Osx-arc Gtk3 Themes "
  installOsxArcThemes
  # 安装 OhMyZsh
  print_info "Install Oh My Zsh "
  installOhMyZsh
  # 配置DNS
  print_info "Configure DNS "
  configDNS
  # 安装字体
  print_info "Install and configure Fonts "
  installFonts
  # 编译安装 ProxyChains-ng
  print_info "Install ProxyChains "
  installProxyChains
  # 安装并配置 Shadowsocksr-Python
  print_info "Install and configure Shadowsocksr "
  installShadowsocksr
  # 编译安装 i3Gaps
  print_info "Install i3Gaps "
  installI3Gaps
  # 编译安装 Polybar
  print_info "Install Polybar "
  installPolybar
  # 安装 MPD , NCMPCPP
  print_info "Install Ncmpcpp Mpd "
  installMpdNcmpcpp
  # 安装 VimPlus
  print_info "Install VimPlus "
  installVimPlus
  # 安装 gksudo 及其需要的依赖 . 由于某种原因 gksudo 被 debian testing 移除 . 但有些地方需要使用 , 故装一下
  print_info "Install Gksudo "
  installGkSudo
  # 其他配置
  print_info "Start needs configure "
  someConfigure
  # 清理临时目录
  print_info "Clear script WorkPath Cache "
  sudo rm -rf $workPath/.cache
  commandSuccess $? "Clear install script Cache "
  # 安装蓝牙驱动
  print_info "Install BCM95342HMB Bluetooth device driver "
  installBluetooth
}

main
