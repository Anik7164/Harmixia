<?php
session_start();
include 'conn.php';
use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception;
require './PHPMailer/src/Exception.php';
require './PHPMailer/src/PHPMailer.php';
require './PHPMailer/src/SMTP.php';

if (isset($_SESSION['user_id'])) {
    header("Location: ..\Website page\index.html");
    exit();
}

if ($_SERVER["REQUEST_METHOD"] == "POST" && isset($_POST['login'])) {
    $email = $_POST['email'];
    $password = $_POST['password'];
    $_SESSION['email']=$email;

    $sql = "SELECT * FROM users WHERE email='$email'";
    $query = mysqli_query($conn, $sql);
    $data = mysqli_fetch_array($query);

    if ($data && password_verify($password, $data['password'])) {
        $otp = rand(100000, 999999);
        $otp_expiry = date("Y-m-d H:i:s", strtotime("+3 minute"));
        $subject= "Your OTP for Login";
        $message="Your OTP is: $otp";

        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $mail->Host = 'smtp.gmail.com';
        $mail->SMTPAuth = true;
        $mail->Username = 'anikmondal340@gmail.com'; //host email 
        $mail->Password = 'llcztliolgphxjej'; // app password of your host email
        $mail->Port = 465;
        $mail->SMTPSecure = 'ssl';
        $mail->isHTML(true);
        $mail->setFrom('anikmondal340@gmail.com', 'Harmixia');//Sender's Email & Name
        $mail->addAddress($email,$name); //Receiver's Email and Name
        $mail->Subject = ("$subject");
        $mail->Body = $message;
        $mail->send();

        $sql1 = "UPDATE users SET otp='$otp', otp_expiry='$otp_expiry' WHERE id=".$data['id'];
        $query1 = mysqli_query($conn, $sql1);

        $_SESSION['temp_user'] = ['id' => $data['id'], 'otp' => $otp];
        header("Location: otp_verification.php");
        exit();
    } else {
        ?>
        <script>
           alert("Invalid Email or Password. Please try again.");
                function navigateToPage() {
                    window.location.href = 'index.php';
                }
                window.onload = function() {
                    navigateToPage();
                }
        </script>
        <?php 
    
    }
}
?><!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harmixia Login</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header>
        <h1>Harmixia</h1>
    </header>
    <div id="container">
        <form method="post" action="index.php">
            <label for="email">Email</label>
            <input type="text" id="email" name="email" placeholder="Enter Your Email" required>
            
            <label for="password">Password</label>
            <input type="password" id="password" name="password" placeholder="Enter Your Password" required>
            
            <input type="submit" name="login" value="Login">
            
            <p>Don't have an account? <a href="registration.php">Sign Up</a></p>
        </form>
    </div>
</body>
</html>
