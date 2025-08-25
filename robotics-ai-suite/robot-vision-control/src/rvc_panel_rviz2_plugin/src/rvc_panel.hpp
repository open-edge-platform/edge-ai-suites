// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#ifndef RVC_PANEL_HPP_
#define RVC_PANEL_HPP_

#ifndef Q_MOC_RUN
#include <memory>

#include "geometry_msgs/msg/twist.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rviz_common/panel.hpp"
#endif

#include <QtCore/QVariant>
#include <QtWidgets/QApplication>
#include <QtWidgets/QDial>
#include <QtWidgets/QHBoxLayout>
#include <QtWidgets/QLabel>
#include <QtWidgets/QSlider>
#include <QtWidgets/QGroupBox>
#include <QtWidgets/QPushButton>
#include <QtWidgets/QSpacerItem>
#include <QtWidgets/QVBoxLayout>
#include <QtWidgets/QWidget>


#include <std_msgs/msg/u_int16.hpp>
#include <std_msgs/msg/float64_multi_array.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <memory>

#include "geometry_msgs/msg/pose.hpp"
#include "rclcpp/rclcpp.hpp"
#include <tf2/buffer_core.h>
#include <geometry_msgs/msg/transform_stamped.hpp>
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "gui_settings/msg/gui_settings_msg.hpp"
#include "rvc_messages/msg/pose_stamped.hpp"

# include <OgreMaterial.h>
# include <OgreRenderTargetListener.h>
# include <OgreSharedPtr.h>


#include <OgreCamera.h>
#include <OgreManualObject.h>
#include <OgreMaterialManager.h>
#include <OgreRectangle2D.h>
#include <OgreRenderSystem.h>
#include <OgreRenderWindow.h>
#include <OgreRoot.h>
#include <OgreSceneNode.h>
#include <OgreTechnique.h>
#include <OgreTextureManager.h>
#include <OgreViewport.h>
#include "state_machine_msgs/msg/state_machine_msgs.hpp" 

#include "sensor_msgs/image_encodings.hpp"

#include "rviz_common/display_context.hpp"
#include "rviz_common/frame_manager_iface.hpp"
#include "rviz_common/render_panel.hpp"
#include "rviz_common/validate_floats.hpp"
#include "rviz_common/uniform_string_stream.hpp"
#include "rviz_rendering/material_manager.hpp"
#include "rviz_rendering/render_window.hpp"

#include "rviz_default_plugins/displays/image/ros_image_texture.hpp"
#include "rviz_default_plugins/displays/image/image_display.hpp"
#include "rviz_default_plugins/displays/image/ros_image_texture_iface.hpp"

#include <image_transport/image_transport.hpp>
namespace rvc_panel
{

class ColorPushButton : public QPushButton
{
public:
    ColorPushButton(const QString &text, QWidget *parent = nullptr)
        : QPushButton(text, parent)
    {
        setAutoFillBackground(true);
    }

    void setTextColor(const QColor &color)
    {
        QPalette palette = this->palette();
        palette.setColor(this->backgroundRole(), color);
        palette.setColor(this->foregroundRole(), color);
        this->setPalette(palette);
    }
};


class RVCPanel : public rviz_common::Panel
{
  Q_OBJECT

public:
  explicit RVCPanel(QWidget * parent = 0);

  virtual void load(const rviz_common::Config & config) override;
  virtual void save(rviz_common::Config config) const override;
  virtual ~RVCPanel();
public Q_SLOTS:
  void enableRobotControllerToggled(bool checked);
  void enableFullCycleToggled(bool checked);
  void enableTrackOnGripperClosingToggled(bool checked);
  void enableSafePositionToggled(bool checked);
  void robotSpeedChanged(int value);
  void mySpin();
  void onInitialize() override;
protected:
    QWidget *verticalLayoutWidget;    
    QVBoxLayout *verticalLayout;
    QHBoxLayout *horizontalLayout;
    QHBoxLayout *horizontalLayoutMain;
    QVBoxLayout *robotSpeedVerticalLayout;
    QDial *RobotSpeedDial;
    QSlider *slider[6];
    QLabel *RobotSpeedLabel;
    QLabel *TopicLabel;
    QString role;
    QVBoxLayout *buttonsVerticalLayout;
    QPushButton *EnableRobotControllerButton;
    QPushButton *EnableFullCycleButton;
    QPushButton *EnableTrackOnGripperClosingButton;
    QPushButton *EnableSafePositionButton;
    QPixmap IPCPm;

    QVBoxLayout *videoVerticalLayout;
    rclcpp::Node::SharedPtr nodeClient;
    rclcpp::Client<std_srvs::srv::Trigger>::SharedPtr reset_robot_client_;


private:
    QSlider *makePidSlider(const QString name, int range);
    void setGUI();
    void publishEverything();

    std::shared_ptr<rclcpp::Node> node_;
    bool enableController;
    bool enableFullcycle;
    bool enableMouseTracking;
    bool enableTrackingOnCloseGripper;
    bool enableHandDetection;
    bool enablePeopleDetection;
    bool safePosition;
    double robotSpeed;
    void setupScreenRectangle();
    void resub0();
    void resub1();

    rclcpp::Publisher<gui_settings::msg::GuiSettingsMsg>::SharedPtr settingPublisher;
    rclcpp::Subscription<gui_settings::msg::GuiSettingsMsg>::SharedPtr settingSubscriber;
    rclcpp::Subscription<std_msgs::msg::UInt16>::SharedPtr actualControllerSubscriber;
    rclcpp::Subscription<state_machine_msgs::msg::StateMachineMsgs>::SharedPtr stateMachineSubscriber0, stateMachineSubscriber1;
    void settingsCallback ( gui_settings::msg::GuiSettingsMsg::SharedPtr  msg );

    gui_settings::msg::GuiSettingsMsg settingMessage;
    std::map<std::string, uint64_t> settingsMap;
    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::TimerBase::SharedPtr state_machine_timer_;

    std::unique_ptr<Ogre::Rectangle2D> screen_rect_;
    Ogre::MaterialPtr material_;

    std::unique_ptr<rviz_default_plugins::displays::ROSImageTextureIface> texture_;

    std::unique_ptr<rviz_common::RenderPanel> render_panel_;
    void topic_callback(sensor_msgs::msg::Image::ConstSharedPtr msg);
    image_transport::Subscriber m_sub_imgs;

    rviz_common::properties::BoolProperty * normalize_property_;
    rviz_common::properties::FloatProperty * min_property_;
    rviz_common::properties::FloatProperty * max_property_;
    rviz_common::properties::IntProperty * median_buffer_size_property_;
    
    virtual void resizeEvent(QResizeEvent *event) override;
    int currentSubscription;
  bool got_float_image_;
};

}  // end namespace 

#endif  // RVC_PANEL_HPP_
