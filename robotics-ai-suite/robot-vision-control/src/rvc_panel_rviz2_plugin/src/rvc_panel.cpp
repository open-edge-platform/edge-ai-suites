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

#include <QPainter>
#include <QSlider>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QTimer>
#include <QCheckBox>
#include <QTimer>

#include "geometry_msgs/msg/twist.hpp"
#include "pluginlib/class_list_macros.hpp"

#include "rvc_panel.hpp"

#include "ament_index_cpp/get_package_share_directory.hpp"


#define P_RANGE (40.0f)
#define ID_RANGE (20.0f)


/** Added adaptative video to the RVC Panel
- the video shown will be shown in this order of priority
  - if AI inference is available
  - if Realsense RGB stream is available
*/

const std::string transport = "compressed";
using namespace std::chrono_literals;

namespace rvc_panel
{
void RVCPanel::setGUI()
{
    std::string icon_path = ament_index_cpp::get_package_share_directory( "rvc_panel_rviz2_plugin") + "/icons/";        

    const QSize sliderSize(76,40);
    const QSize buttonSize(110,50);
    verticalLayoutWidget = new QWidget;
    verticalLayoutWidget->setObjectName(QString::fromUtf8("verticalLayoutWidget"));
    verticalLayoutWidget->setGeometry(QRect(90, 430, 491, 211));
    verticalLayout = new QVBoxLayout(verticalLayoutWidget);
    verticalLayout->setObjectName(QString::fromUtf8("verticalLayout"));
    //verticalLayout->setContentsMargins(15, 5, 5, 5);
    verticalLayout->setContentsMargins(15, 0, 5, 0);

    horizontalLayout = new QHBoxLayout;
    horizontalLayout->setObjectName(QString::fromUtf8("horizontalLayout"));
    horizontalLayoutMain = new QHBoxLayout;
    horizontalLayoutMain->setObjectName(QString::fromUtf8("horizontalLayoutMain"));
    horizontalLayoutMain->setSizeConstraint(QLayout::SetMaximumSize);

//======
    buttonsVerticalLayout = new QVBoxLayout();
    buttonsVerticalLayout->setObjectName(QString::fromUtf8("buttonsVerticalLayout"));
    
    EnableRobotControllerButton = new QPushButton(verticalLayoutWidget);
    EnableRobotControllerButton->setObjectName(QString::fromUtf8("EnableRobotControllerButton"));
    

    EnableRobotControllerButton->setCheckable(true);
    EnableRobotControllerButton->setChecked(false);


    QIcon iconPower,icon,iconPushButton;
    std::string onIcon = icon_path+"classes/PowerOn.png";
    std::string offIcon = icon_path+"classes/PowerOff.png";

    iconPower.addFile(QString::fromUtf8(offIcon.c_str()), QSize(), QIcon::Normal, QIcon::Off);
    iconPower.addFile(QString::fromUtf8(onIcon.c_str()), QSize(), QIcon::Normal, QIcon::On);
    EnableRobotControllerButton->setIcon(iconPower);
    EnableRobotControllerButton->setIconSize(buttonSize);
    EnableRobotControllerButton->setFlat(true);
    EnableRobotControllerButton->setStyleSheet("QPushButton {border-style: outset; text-align:left; border-width: 0px;}");


    onIcon = icon_path+"classes/flipswitchon.png";
    offIcon = icon_path+"classes/flipswitchoff.png";
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " icon %s", offIcon.c_str() );
    icon.addFile(QString::fromUtf8(offIcon.c_str()), QSize(), QIcon::Normal, QIcon::Off);
    icon.addFile(QString::fromUtf8(onIcon.c_str()), QSize(), QIcon::Normal, QIcon::On);
    
    
    
    buttonsVerticalLayout->addWidget(EnableRobotControllerButton);

    EnableFullCycleButton = new QPushButton(verticalLayoutWidget);
    EnableFullCycleButton->setText("TrackOnly/FullCycle");
    EnableFullCycleButton->setCheckable(true);
    EnableFullCycleButton->setChecked(true);
    EnableFullCycleButton->setIcon(icon);
    EnableFullCycleButton->setIconSize(sliderSize);
    EnableFullCycleButton->setFlat(true);
    EnableFullCycleButton->setStyleSheet("QPushButton {border-style: outset; text-align:left;  border-width: 0px;}");
    
    
    buttonsVerticalLayout->addWidget(EnableFullCycleButton);


    EnableTrackOnGripperClosingButton = new QPushButton(verticalLayoutWidget);
    EnableTrackOnGripperClosingButton->setText("Track on close");
    EnableTrackOnGripperClosingButton->setCheckable(true);
    EnableTrackOnGripperClosingButton->setChecked(false);
    EnableTrackOnGripperClosingButton->setIcon(icon);
    EnableTrackOnGripperClosingButton->setIconSize(sliderSize);
    EnableTrackOnGripperClosingButton->setFlat(true);
    EnableTrackOnGripperClosingButton->setStyleSheet("QPushButton {border-style: outset; text-align:left;  border-width: 0px;}");

    buttonsVerticalLayout->addWidget(EnableTrackOnGripperClosingButton);

    EnableSafePositionButton = new QPushButton(verticalLayoutWidget);
    EnableSafePositionButton->setText("Safe position");
    EnableSafePositionButton->setCheckable(true);
    EnableSafePositionButton->setChecked(true);
    EnableSafePositionButton->setIcon(icon);
    EnableSafePositionButton->setIconSize(sliderSize);
    EnableSafePositionButton->setFlat(true);
    EnableSafePositionButton->setStyleSheet("QPushButton {border-style: outset; text-align:left;  border-width: 0px;}");

//    buttonsVerticalLayout->addWidget(EnableSafePositionButton);
    horizontalLayoutMain->addLayout(buttonsVerticalLayout);

    robotSpeedVerticalLayout = new QVBoxLayout;
    robotSpeedVerticalLayout->setObjectName(QString::fromUtf8("robotSpeedVerticalLayout"));
    robotSpeedVerticalLayout->setSizeConstraint(QLayout::SetMaximumSize);
    RobotSpeedDial = new QDial;
    RobotSpeedDial->setObjectName(QString::fromUtf8("RobotSpeedDial"));
    RobotSpeedDial->setValue(90);
    RobotSpeedDial->setNotchesVisible(true);

    QSizePolicy sizePolicyMax(QSizePolicy::Maximum, QSizePolicy::Preferred);
    sizePolicyMax.setHorizontalStretch(0);
    sizePolicyMax.setVerticalStretch(0);
    sizePolicyMax.setHeightForWidth(RobotSpeedDial->sizePolicy().hasHeightForWidth());
    RobotSpeedDial->setSizePolicy(sizePolicyMax);


    robotSpeedVerticalLayout->addWidget(RobotSpeedDial);

    RobotSpeedLabel = new QLabel(verticalLayoutWidget);
    RobotSpeedLabel->setText("Robot Speed");
    RobotSpeedLabel->setAlignment(Qt::AlignLeft);
    robotSpeedVerticalLayout->addWidget(RobotSpeedLabel);

  

    QLabel * intelIcon = new QLabel(verticalLayoutWidget);
    intelIcon->setAlignment(Qt::AlignRight);
    std::string intelIconString = icon_path + "Intel-logo-2022.png";
    QImage image(intelIconString.c_str());
    QPixmap pm = QPixmap::fromImage(image);
    intelIcon->setPixmap(pm);
    //    intelIcon->setScaledContents(true);
    intelIcon->setAlignment(Qt::AlignBottom|Qt::AlignHCenter);
    robotSpeedVerticalLayout->addWidget(intelIcon);
    

    
    horizontalLayoutMain->addLayout(robotSpeedVerticalLayout);

    //=====
    horizontalLayout->addLayout(horizontalLayoutMain);
    verticalLayout->addLayout(horizontalLayout);

    videoVerticalLayout = new QVBoxLayout();
    videoVerticalLayout->setObjectName(QString::fromUtf8("videoVerticalLayout"));
    render_panel_ = std::make_unique<rviz_common::RenderPanel>(this);

    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " RVCPanel Constructor: TRYING TO RESIZE" );

    render_panel_->resize(640, 480);
    render_panel_->initialize(getDisplayContext());


  static int counter = 0;
  render_panel_->getRenderWindow()->setObjectName(
    "ImageDisplayRenderWindowDario" + QString::number(counter++));

    videoVerticalLayout->addWidget(render_panel_.get());

    TopicLabel = new QLabel(verticalLayoutWidget);

    QSizePolicy sizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    sizePolicy.setHorizontalStretch(0);
    sizePolicy.setVerticalStretch(0);
    sizePolicy.setHeightForWidth(RobotSpeedLabel->sizePolicy().hasHeightForWidth());
    TopicLabel->setSizePolicy(sizePolicy);        
    TopicLabel->setAlignment(Qt::AlignCenter);

    videoVerticalLayout->addWidget(TopicLabel);

    verticalLayout->addLayout(videoVerticalLayout);
    
    setLayout(verticalLayout);

    this->setWindowTitle(QApplication::translate("Dialog", "Dialog", nullptr));
    TopicLabel->setText("No Topic set");
 
    render_panel_->resize(640, 480);

    connect(EnableRobotControllerButton, SIGNAL(toggled(bool)), this, SLOT(enableRobotControllerToggled(bool)));
    connect(EnableFullCycleButton, SIGNAL(toggled(bool)), this, SLOT(enableFullCycleToggled(bool)));
    connect(EnableTrackOnGripperClosingButton, SIGNAL(toggled(bool)), this, SLOT(enableTrackOnGripperClosingToggled(bool)));
    connect(RobotSpeedDial, SIGNAL(valueChanged(int)), this, SLOT(robotSpeedChanged(int)));
}


RVCPanel::RVCPanel(QWidget * parent)
: rviz_common::Panel(parent)
    , enableController(false)
    , enableFullcycle(true)
    , enableTrackingOnCloseGripper(false)
    , robotSpeed(2)
    , currentSubscription(-1)
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " RVCPanel Constructor" );
    texture_ = std::make_unique<rviz_default_plugins::displays::ROSImageTexture>();
}

RVCPanel::~RVCPanel()
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " RVCPanel ~DEstructor" );
}

void RVCPanel::setupScreenRectangle()
{
  static int count = 0;
  rviz_common::UniformStringStream ss;
  ss << "ImageDisplayObjectDario" << count++;

  screen_rect_ = std::make_unique<Ogre::Rectangle2D>(true);
  screen_rect_->setRenderQueueGroup(Ogre::RENDER_QUEUE_OVERLAY - 1);
  screen_rect_->setCorners(-1.0f, 1.0f, 1.0f, -1.0f);

  ss << "MaterialDario";
  material_ = rviz_rendering::MaterialManager::createMaterialWithNoLighting(ss.str());
  material_->setSceneBlending(Ogre::SBT_REPLACE);
  material_->setDepthWriteEnabled(false);
  material_->setDepthCheckEnabled(false);

  Ogre::TextureUnitState * tu =
    material_->getTechnique(0)->getPass(0)->createTextureUnitState();
  tu->setTextureName(texture_->getName());
  tu->setTextureFiltering(Ogre::TFO_NONE);

  material_->setCullingMode(Ogre::CULL_NONE);
  Ogre::AxisAlignedBox aabInf;
  aabInf.setInfinite();
  screen_rect_->setBoundingBox(aabInf);
  screen_rect_->setMaterial(material_);

}

void RVCPanel::onInitialize()
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " RVCPanel onInitialize" );    
    this->resize(940,980);
    this->setupScreenRectangle();
    this->setGUI();

    node_ =getDisplayContext()->getRosNodeAbstraction().lock()->get_raw_node();

    nodeClient = std::make_shared<rclcpp::Node>("robotDemoRvizPluginNode");
    reset_robot_client_ = nodeClient->create_client<std_srvs::srv::Trigger>("io_and_status_controller/resend_robot_program", rmw_qos_profile_services_default);

    auto inference_rmw_qos = rmw_qos_profile_sensor_data;

    auto qostransientlocal = rclcpp::QoS (rclcpp::KeepLast ( 1 ),rmw_qos_profile_default);
    qostransientlocal.transient_local(); // guarantes the last message is latched
    settingPublisher = node_->create_publisher<gui_settings::msg::GuiSettingsMsg>(
        "/computer_vision_robot_demo/settings", qostransientlocal);
    settingSubscriber = node_->create_subscription<gui_settings::msg::GuiSettingsMsg> (
        "/computer_vision_robot_demo/settings",
    qostransientlocal,
        std::bind ( &RVCPanel::settingsCallback, this, std::placeholders::_1 ) );
    std::string ns = nodeClient->get_namespace();
    std::string topic_prefix = std::string ("camera/camera") + ns.substr(1, ns.size() - 1) + std::string("/");

    m_sub_imgs = image_transport::create_subscription(node_.get(),
		    topic_prefix + std::string("color/image_raw"),
		    std::bind(&RVCPanel::topic_callback, this, std::placeholders::_1),transport,inference_rmw_qos);

   QTimer* output_timer = new QTimer( this );
   connect( output_timer, SIGNAL( timeout() ), this, SLOT( mySpin() ));
   output_timer->start( 100 );


    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"), " RVCPanel onInitialize DONE" );
    render_panel_->getRenderWindow()->setupSceneAfterInit(
        [this](Ogre::SceneNode * scene_node) {
          scene_node->attachObject(screen_rect_.get());
        });
}

void RVCPanel::settingsCallback ( gui_settings::msg::GuiSettingsMsg::SharedPtr  msg )                                 
{                                                                                                                     
                                                                                                                      
    enableController = msg->enable_controller;                                                                        
    robotSpeed = msg->robot_speed;                                                                                    
    safePosition = msg->enable_safe_position;
    enableFullcycle = msg->enable_fullcycle;
    enableTrackingOnCloseGripper = msg->enable_tracking_on_close_gripper;

    EnableRobotControllerButton->setChecked(enableController);
    EnableFullCycleButton->setChecked(enableFullcycle);

    EnableTrackOnGripperClosingButton->setChecked(enableTrackingOnCloseGripper);
    EnableSafePositionButton->setChecked(safePosition);

    int value = (int)5*(20.0-robotSpeed);
    RobotSpeedDial->setValue(value);
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"settingsCallback: received robotSpeed %f, converted to dial int %d...", robotSpeed, value);

}

void RVCPanel::mySpin()
{

    QString label;

    //RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"START");
    int inferenceDetectionPublishers = node_->count_publishers("annotated_image");
    int realsenseRgbPublishers = node_->count_publishers("camera/color/image_raw");
#ifndef BUILD_SENSOR_DATA
        auto qos_profile = rmw_qos_profile_default;
#else
        auto qos_profile = rmw_qos_profile_sensor_data;
#endif

    if ( inferenceDetectionPublishers > 0 && currentSubscription != 1)
    {

        RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"Switching topic to annotated_image... with transport %s",transport.c_str());
        m_sub_imgs.shutdown(); //unsubscribe...

        if (node_->count_publishers("annotated_image/compressed") == 0)
            m_sub_imgs = image_transport::create_subscription(node_.get(), "annotated_image", std::bind(&RVCPanel::topic_callback, this, std::placeholders::_1),
             "raw", qos_profile);
        else
            m_sub_imgs = image_transport::create_subscription(node_.get(), "annotated_image", std::bind(&RVCPanel::topic_callback, this, std::placeholders::_1),
                 transport, qos_profile);
        currentSubscription = 1;
//        resizeEvent(nullptr);
        TopicLabel->setText("AI Object Detection");                
        RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"Switching topic to annotated_image...DONE");
    }
    else if ( inferenceDetectionPublishers == 0 && realsenseRgbPublishers > 0 && currentSubscription != 0)
    {

        RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"Switching topic to /camera/color/image_raw...");
        m_sub_imgs.shutdown(); //unsubscribe...
        m_sub_imgs = image_transport::create_subscription(node_.get(), "camera/color/image_raw", std::bind(&RVCPanel::topic_callback, this, std::placeholders::_1), transport, qos_profile);
        currentSubscription = 0;
//        resizeEvent(nullptr);
        TopicLabel->setText("Realsense RGB Camera");
        RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"Switching topic to /camera/color/image_raw...DONE");
    }
        
//     RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"Current subscription topic: %s",m_sub_imgs->get_topic_name());
   //RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"END");
}

void RVCPanel::resizeEvent ( QResizeEvent* event )
{
    (void)event;
    static bool firstResize = true;

    if (firstResize)
    {
        render_panel_->resize(640,480);
        firstResize = false;
    }

    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"resizeEvent...");
//  if ((initialized == false) || (render_panel_ == nullptr))
    if ((render_panel_ == nullptr))
        return;
  // make sure the aspect ratio of the image is preserved
    float win_width = render_panel_->width();
    float win_height = render_panel_->height();

    float img_width = texture_->getWidth();
    float img_height = texture_->getHeight();

    if (img_width != 0 && img_height != 0 && win_width != 0 && win_height != 0) {
      float img_aspect = img_width / img_height;
      float win_aspect = win_width / win_height;

      if (img_aspect > win_aspect) {
        screen_rect_->setCorners(
          -1.0f, 1.0f * win_aspect / img_aspect, 1.0f, -1.0f * win_aspect / img_aspect, false);
      } else {
        screen_rect_->setCorners(
          -1.0f * img_aspect / win_aspect, 1.0f, 1.0f * img_aspect / win_aspect, -1.0f, false);
      }
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"resizeEvent...DONE win %f:%f img %f:%f win aspect %f img aspect %f" , win_width, win_height, img_width, img_height, win_aspect, img_aspect);
    }

    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"resizeEvent...DONE win %f:%f img %f:%f" , win_width, win_height, img_width, img_height);
}
void RVCPanel::topic_callback(sensor_msgs::msg::Image::ConstSharedPtr msg)
{
    //RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"received image...");
    texture_->addMessage(std::move(msg));
    texture_->update();
    static bool first =true;
    
    if (first)
    {
        first = false;
        resizeEvent(nullptr);
    }
} 
void RVCPanel::robotSpeedChanged(int value)
{
    robotSpeed = 20.0 - (value / 5.0);
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"speed dial value: %d %f", value, robotSpeed);
    publishEverything();
}

void RVCPanel::enableRobotControllerToggled(bool checked)
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"enableRobotControllerToggled: %s",checked?"True":"False");
    enableController = checked;
    publishEverything();
}

void RVCPanel::enableFullCycleToggled(bool checked)
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"enableFullCycleToggled: %s",checked?"True":"False");
    enableFullcycle = checked;
    publishEverything();

}
void RVCPanel::enableTrackOnGripperClosingToggled(bool checked)
{
    RCLCPP_INFO(rclcpp::get_logger("rvizPlugin"),"enableTrackOnGripperClosingToggled: %s",checked?"True":"False");
    enableTrackingOnCloseGripper = checked;
    publishEverything();
}

void RVCPanel::publishEverything()
{
// the smaller, the faster
#define MAX_SPEED 0.002
    if (robotSpeed < MAX_SPEED)
    {
        RCLCPP_INFO(node_->get_logger(), "LIMITING robotSpeed to 0.07!!");
        robotSpeed = MAX_SPEED;
    }

    settingMessage.enable_controller = enableController;
    settingMessage.robot_speed = robotSpeed;
    settingMessage.enable_safe_position = safePosition;
    settingMessage.enable_fullcycle = enableFullcycle;
    settingMessage.enable_tracking_on_close_gripper = enableTrackingOnCloseGripper;

    settingPublisher->publish(settingMessage);
    RCLCPP_INFO(node_->get_logger(), "PUBLISHING SETTINGS!");
}


// Save all configuration data from this panel to the given
// Config object.  It is important here that you call save()
// on the parent class so the class id and panel name get saved.
void RVCPanel::save(rviz_common::Config config) const
{
  rviz_common::Panel::save(config);
  //config.mapSetValue("Topic", output_topic_);
}

// Load all configuration data for this panel from the given Config object.
void RVCPanel::load(const rviz_common::Config & config)
{
  rviz_common::Panel::load(config);
#if 0  
  QString topic;
  if (config.mapGetString("Topic", &topic)) {
    output_topic_editor_->setText(topic);
    updateTopic();
  }
#endif
}

}  // end namespace rviz_plugin_tutorials

// Tell pluginlib about this class.  Every class which should be
// loadable by pluginlib::ClassLoader must have these two lines
// compiled in its .cpp file, outside of any namespace scope.
PLUGINLIB_EXPORT_CLASS(rvc_panel::RVCPanel, rviz_common::Panel)
// END_TUTORIAL
